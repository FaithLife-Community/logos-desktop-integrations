#if LOGOS_LOCAL_DATA
import Foundation
import CryptoKit

extension LocalLogosData {
    static let showcaseTypes = Set([
        "text.monograph", "text.monograph.systematic-theology", "text.monograph.biblical-theology",
        "text.monograph.church-history", "text.monograph.biography", "text.monograph.devotional",
        "text.monograph.collected-work", "text.monograph.sermons", "text.monograph.lecture",
        "text.monograph.introduction.new-testament", "text.monograph.introduction.old-testament"
    ])
    static func dailyScore(_ key: String) -> String {
        SHA256.hash(data: Data(key.utf8)).map { String(format: "%02x", $0) }.joined()
    }
    static func readPriorities(data: URL, documents: URL) -> [String: (Int, String)] {
        let queries = [
            (data.appendingPathComponent("KeyLinkManager/keylinkmanager.db"),
             "SELECT r.ResourceId, k.Rank, k.Language FROM KeyLinkRules k JOIN Resources r ON r.Id = k.Resource"),
            (documents.appendingPathComponent("KeyLinkManager/KeyLinkSyncManager.db"),
             "SELECT ResourceId, Rank, Language FROM KeyLinkRules WHERE IsDeleted = 0 AND ResourceId IS NOT NULL")
        ]
        for (path, sql) in queries {
            guard let db = try? ReadOnlyDatabase(path), let rows = try? db.rows(sql) else { continue }
            var ranks: [String: (Int, String)] = [:]
            for row in rows {
                let id = row.text("ResourceId"), rank = Int(row.number("Rank"))
                if let old = ranks[id], old.0 <= rank { continue }
                let language = row.text("Language")
                ranks[id] = (rank, ["el", "grc"].contains(language) ? "g" : (["he", "hbo", "arc"].contains(language) ? "h" : language))
            }
            if !ranks.isEmpty { return ranks }
        }
        return [:]
    }
    static func factbook(_ query: String, root: String) throws -> [LibraryItem] {
        let (data, _) = try locations(root)
        let words = query.lowercased().split(whereSeparator: { !$0.isLetter && !$0.isNumber }).map(String.init)
        guard let first = words.first else { return [] }
        let db = try ReadOnlyDatabase(data.appendingPathComponent("AutoComplete/AutoComplete.db"))
        let having = words.dropFirst().map { _ in " AND group_concat(lower(l.LabelText),'|') LIKE ?" }.joined()
        let sql = """
            SELECT t.TermId, t.Reference, max(lower(l.LabelText) = ?) AS Exact,
                   (SELECT count(*) FROM MentionReferences m WHERE m.TermId = t.TermId) AS Mentions
            FROM LabelWords w JOIN Labels l ON l.LabelId = w.LabelId JOIN Terms t ON t.TermId = l.TermId
            WHERE w.LanguageId = 1 AND w.FoldedText >= ? AND w.FoldedText < ? AND l.LanguageId = 1
            GROUP BY t.TermId HAVING 1 \(having) ORDER BY Exact DESC, Mentions DESC LIMIT 8
            """
        return try db.rows(sql, [words.joined(separator: " "), first, first + "\u{ffff}"] + words.dropFirst().map { "%\($0)%" }).map { row in
            let id = String(Int(row.number("TermId")))
            let title = try db.rows("SELECT LabelText FROM Labels WHERE TermId = ? AND IsPrimary = 1 AND LanguageId = 1", [id]).first?.text("LabelText") ?? row.text("Reference")
            let description = try db.rows("SELECT Description FROM Descriptions WHERE TermId = ? AND LanguageId = 1", [id]).first?.text("Description") ?? ""
            return LibraryItem(id: "factbook:\(id)", title: title, subtitle: description,
                url: "logos4:Factbook;id=ref%3A\(encoded(row.text("Reference")));lens=all", category: "factbook")
        }
    }
    static func sermonCommentaries(documents: URL, records: [[String: Any]], books: [String: LibraryItem]) throws -> [LibraryItem] {
        let db = try ReadOnlyDatabase(documents.appendingPathComponent("Documents/Sermon/Sermon.db"))
        var sermons = try db.rows("SELECT Id, Title, Date, ModifiedDate, OccasionsJson FROM Documents WHERE IsDeleted = 0 AND coalesce(IsTemplate,0) = 0 ORDER BY ModifiedDate DESC")
        let formatter = DateFormatter(); formatter.dateFormat = "yyyy-MM-dd"
        let today = formatter.string(from: Date())
        func date(_ sermon: [String: Any]) -> String {
            if let data = sermon.text("OccasionsJson").data(using: .utf8),
               let occasions = (try? JSONSerialization.jsonObject(with: data)) as? [[String: Any]] {
                let dates = occasions.compactMap { $0["date"] as? String }.sorted()
                if let date = dates.first(where: { $0 >= today }) ?? dates.last { return date }
            }
            return sermon.text("Date")
        }
        sermons.sort { left, right in
            let a = date(left), b = date(right)
            let aFuture = !a.isEmpty && a >= today, bFuture = !b.isEmpty && b >= today
            if aFuture != bFuture { return aFuture }
            return aFuture ? a < b : a > b
        }
        for sermon in sermons {
            let id: String
            if let bytes = sermon["Id"] as? Data { id = bytes.map { String(format: "%02x", $0) }.joined() }
            else { id = (sermon["Id"] as? NSNumber)?.stringValue ?? sermon.text("Id") }
            // Compare hex as well as text so .NET document IDs remain valid bound values.
            let blocks = try db.rows("SELECT PassageJson FROM Blocks WHERE (DocumentId = ? OR lower(hex(DocumentId)) = ?) AND IsDeleted = 0 AND PassageJson IS NOT NULL ORDER BY Rank", [id, id.lowercased()])
            var reference: String?
            for block in blocks {
                guard let data = block.text("PassageJson").data(using: .utf8),
                      let json = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any],
                      let ref = json["reference"] as? [String: Any], let raw = ref["raw"] as? String else { continue }
                reference = raw; break
            }
            guard let reference, let point = ReadingDetails.referenceParts(reference).first else { continue }
            let covering = records.filter { $0.text("Type") == "text.monograph.commentary.bible" && covers($0.text("ReferenceSupersets"), point: point) }
            let mine = covering.filter { $0.number("UserRating") >= 4 }
            let candidates = (mine.isEmpty ? covering.filter { $0.number("CommunityRatingCount") >= 15 } : mine).sorted {
                if $0.number("UserRating") != $1.number("UserRating") { return $0.number("UserRating") > $1.number("UserRating") }
                return $0.number("CommunityRating") > $1.number("CommunityRating")
            }
            return candidates.prefix(mine.isEmpty ? 3 : 12).compactMap { row in
                guard var item = books[row.text("ResourceId")] else { return nil }
                item.id = "commentary:\(item.id)"; item.category = "commentary"
                item.subtitle = "\(sermon.text("Title")) · \(ReadingDetails.readable(reference))"
                item.url += ";ref=\(encoded(reference))"
                return item
            }
        }
        return []
    }
    private static func covers(_ supersets: String, point: [Int]) -> Bool {
        func key(_ numbers: [Int], fill: Int) -> [Int] { Array((numbers + [fill, fill, fill]).prefix(3)) }
        let target = key(point, fill: 1)
        return supersets.split(separator: "\t").contains { range in
            guard range.hasPrefix("bible") else { return false }
            let parts = ReadingDetails.referenceParts(String(range))
            guard let start = parts.first, let end = parts.last else { return false }
            let first = key(start, fill: 0), last = key(end, fill: 999)
            return !target.lexicographicallyPrecedes(first) && !last.lexicographicallyPrecedes(target)
        }
    }
}
#endif
