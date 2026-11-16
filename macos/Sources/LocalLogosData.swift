#if LOGOS_LOCAL_DATA
import Foundation
import SQLite3

// Keep every Logos-folder path and database operation inside this compile-time boundary.
final class ReadOnlyDatabase {
    private var handle: OpaquePointer?
    init(_ path: URL) throws {
        guard sqlite3_open_v2(path.path, &handle, SQLITE_OPEN_READONLY | SQLITE_OPEN_NOMUTEX, nil) == SQLITE_OK else {
            let message = handle.map { String(cString: sqlite3_errmsg($0)) } ?? "Cannot open database"
            sqlite3_close(handle)
            handle = nil
            throw IntegrationError("\(path.lastPathComponent): \(message)")
        }
        sqlite3_busy_timeout(handle, 750)
    }
    deinit { sqlite3_close(handle) }
    func rows(_ sql: String, _ arguments: [String] = []) throws -> [[String: Any]] {
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(handle, sql, -1, &statement, nil) == SQLITE_OK else {
            throw IntegrationError(String(cString: sqlite3_errmsg(handle)))
        }
        defer { sqlite3_finalize(statement) }
        for (offset, value) in arguments.enumerated() {
            let transient = unsafeBitCast(-1, to: sqlite3_destructor_type.self)
            _ = value.withCString { sqlite3_bind_text(statement, Int32(offset + 1), $0, -1, transient) }
        }
        var output: [[String: Any]] = []
        while true {
            let status = sqlite3_step(statement)
            if status == SQLITE_DONE { return output }
            guard status == SQLITE_ROW else { throw IntegrationError(String(cString: sqlite3_errmsg(handle))) }
            var row: [String: Any] = [:]
            for index in 0..<sqlite3_column_count(statement) {
                let key = String(cString: sqlite3_column_name(statement, index))
                switch sqlite3_column_type(statement, index) {
                case SQLITE_TEXT: row[key] = String(cString: sqlite3_column_text(statement, index))
                case SQLITE_INTEGER: row[key] = Int(sqlite3_column_int64(statement, index))
                case SQLITE_FLOAT: row[key] = sqlite3_column_double(statement, index)
                case SQLITE_BLOB:
                    if let bytes = sqlite3_column_blob(statement, index) {
                        row[key] = Data(bytes: bytes, count: Int(sqlite3_column_bytes(statement, index)))
                    }
                default: break
                }
            }
            output.append(row)
        }
    }
}

extension Dictionary where Key == String, Value == Any {
    func text(_ key: String) -> String { self[key] as? String ?? "" }
    func number(_ key: String) -> Double { (self[key] as? NSNumber)?.doubleValue ?? 0 }
}

struct LocalReadResult {
    var items: [LibraryItem] = []
    var messages: [String] = []
}

enum LocalLogosData {
    static func encoded(_ text: String) -> String {
        text.addingPercentEncoding(withAllowedCharacters: CharacterSet.alphanumerics.union(CharacterSet(charactersIn: ":,."))) ?? text
    }
    static func locations(_ override: String) throws -> (URL, URL) {
        let manager = FileManager.default
        let support = manager.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support")
        let roots = override.isEmpty ? ["Logos4", "Logos", "Verbum"].map { support.appendingPathComponent($0) } :
            [URL(fileURLWithPath: NSString(string: override).expandingTildeInPath)]
        var candidates: [(Date, URL, URL)] = []
        for root in roots {
            let data = root.appendingPathComponent("Data")
            for user in (try? manager.contentsOfDirectory(at: data, includingPropertiesForKeys: nil)) ?? [] {
                let catalog = user.appendingPathComponent("LibraryCatalog/catalog.db")
                if let attributes = try? manager.attributesOfItem(atPath: catalog.path),
                   let modified = attributes[.modificationDate] as? Date {
                    candidates.append((modified, user, root.appendingPathComponent("Documents/\(user.lastPathComponent)")))
                }
            }
        }
        guard let newest = candidates.max(by: { $0.0 < $1.0 }) else {
            throw IntegrationError("No Logos catalog found. In Settings, choose the Logos folder containing Data and Documents (usually ~/Library/Application Support/Logos4).")
        }
        return (newest.1, newest.2)
    }
    static func read(root: String) -> LocalReadResult {
        var result = LocalReadResult()
        do {
            let (data, documents) = try locations(root)
            let catalog = try ReadOnlyDatabase(data.appendingPathComponent("LibraryCatalog/catalog.db"))
            let records = try catalog.rows("""
                SELECT r.ResourceId, coalesce(nullif(r.UserTitle,''), r.Title) AS Title,
                       coalesce(nullif(r.UserAbbreviatedTitle,''), r.AbbreviatedTitle) AS Abbreviation,
                       r.Authors, r.Type, r.UseCount, r.Series, r.CommunityRating, r.CommunityRatingCount,
                       r.UserRating, r.LastAccessed, r.ReferenceSupersets,
                       (SELECT group_concat(t.Value, ' ') FROM RecordTraits rt JOIN Traits t ON t.TraitId = rt.TraitId WHERE rt.RecordId = r.RecordId) AS Traits,
                       (SELECT group_concat(AlternateResourceId, ' ') FROM AlternateResourceIds a WHERE a.RecordId = r.RecordId) AS Links,
                       EXISTS(SELECT 1 FROM Images i WHERE i.RecordId = r.RecordId AND i.Image IS NOT NULL) AS HasCover
                FROM Records r WHERE r.Availability IN (1,2) AND r.ResourceId NOT LIKE 'RVI:%'
                    AND r.Type NOT LIKE 'lbx.reverse-interlinear%' ORDER BY r.UseCount DESC
                """)
            let priorities = readPriorities(data: data, documents: documents)
            var books: [String: LibraryItem] = [:]
            for row in records {
                let id = row.text("ResourceId")
                guard books[id] == nil else { continue }
                let links = row.text("Links").split(separator: " ").map(String.init)
                let link = links.first { !$0.lowercased().hasPrefix("lls:") }
                    ?? links.first.map { String($0.dropFirst(4)).lowercased() }
                    ?? id.split(separator: ":", maxSplits: 1).last.map(String.init)?.lowercased() ?? id
                let category = row.text("Type") == "lbx.calendar-devotional" ? "devotional" : "book"
                var item = LibraryItem(id: id, title: row.text("Title"), subtitle: row.text("Authors").replacingOccurrences(of: "\t", with: ", "),
                                       url: "logosres:\(encoded(link))", category: category)
                item.resourceID = id
                item.abbreviation = row.text("Abbreviation")
                item.rating = row.number("CommunityRating")
                item.kind = row.text("Type")
                item.priority = priorities[id]?.0
                item.uses = Int(row.number("UseCount"))
                item.language = priorities[id]?.1
                if item.language == nil || item.language == "" {
                    let traits = row.text("Traits")
                    item.language = (traits.contains("+g") ? "g" : "") + (traits.contains("+h") || traits.contains("supports-bdb") ? "h" : "")
                }
                books[id] = item
                result.items.append(item)
            }
            func section(_ name: String, _ operation: () throws -> [LibraryItem]) {
                do { result.items += try operation() }
                catch { result.messages.append("\(name): \(error.localizedDescription)") }
            }
            section("Layouts") {
                try ReadOnlyDatabase(documents.appendingPathComponent("LayoutManager/layouts.db"))
                    .rows("SELECT DISTINCT Title FROM Layouts WHERE IsDeleted = 0 AND Title <> '' AND Title <> 'Application Closed'")
                    .map { LibraryItem(id: "layout:\($0.text("Title"))", title: $0.text("Title"),
                                       url: SharedStore.commandURL(layoutCommand($0.text("Title"))), category: "layout") }
            }
            section("Reading plans") { try plans(documents, books: books) }
            section("Sermon commentaries") { try sermonCommentaries(documents: documents, records: records, books: books) }
            section("History") {
                let rows = try ReadOnlyDatabase(data.appendingPathComponent("HistoryManager/history.db"))
                    .rows("SELECT Title, Subtitle, Bookmark FROM History WHERE IsDeleted = 0 AND Bookmark LIKE 'Resource|%' ORDER BY LastVisited DESC LIMIT 100")
                var seen = Set<String>()
                return rows.compactMap { row in
                    let fields = Dictionary(row.text("Bookmark").split(separator: "|").dropFirst().compactMap { part -> (String, String)? in
                        let pair = part.split(separator: "=", maxSplits: 1).map(String.init)
                        return pair.count == 2 ? (pair[0], pair[1]) : nil
                    }, uniquingKeysWith: { _, new in new })
                    guard let id = fields["Id"], seen.insert(id).inserted, var item = books[id] else { return nil }
                    item.id = "recent:\(id)"
                    item.category = "recent"
                    if let ref = fields["Reference"]?.removingPercentEncoding, !ref.isEmpty { item.url += ";ref=\(encoded(ref))" }
                    return item
                }
            }
            section("Showcase") {
                var read = Set<String>()
                let progress = try ReadOnlyDatabase(data.appendingPathComponent("ReadingProgressManager/readingprogressmanager.db"))
                for row in try progress.rows("SELECT ResourceId FROM ResourceReadingProgress WHERE IsDeleted = 0 UNION SELECT ResourceId FROM ReadingStatus WHERE PercentageRead > 0") { read.insert(row.text("ResourceId")) }
                let candidates = records.filter {
                    !read.contains($0.text("ResourceId")) && $0.number("UseCount") == 0 && $0["LastAccessed"] == nil &&
                    $0["UserRating"] == nil && $0.number("CommunityRatingCount") >= 15 && $0.number("HasCover") == 1 && showcaseTypes.contains($0.text("Type"))
                }.sorted {
                    ($0.number("CommunityRating") * $0.number("CommunityRatingCount") + 3.6 * 30) / ($0.number("CommunityRatingCount") + 30) >
                    ($1.number("CommunityRating") * $1.number("CommunityRatingCount") + 3.6 * 30) / ($1.number("CommunityRatingCount") + 30)
                }
                var authors = Set<String>(), series = Set<String>()
                var chosen: [LibraryItem] = []
                for row in candidates {
                    let author = row.text("Authors").components(separatedBy: "\t").first ?? ""
                    let collection = row.text("Series")
                    guard author.isEmpty || !authors.contains(author), collection.isEmpty || !series.contains(collection),
                          var book = books[row.text("ResourceId")] else { continue }
                    authors.insert(author); series.insert(collection)
                    book.id = "showcase:\(book.id)"; book.category = "showcase"
                    chosen.append(book)
                    if chosen.count == 36 { break }
                }
                let formatter = DateFormatter(); formatter.dateFormat = "yyyy-MM-dd"
                let day = formatter.string(from: Date())
                return Array(chosen.sorted { dailyScore(day + $0.id) < dailyScore(day + $1.id) }.prefix(12))
            }
            // Bound artwork memory even for libraries with tens of thousands of books.
            // Load visible-widget content first, then a small set of frequently used books.
            var coverCache: [String: Data] = [:]
            let featured = result.items.filter { ["plan", "devotional", "showcase", "commentary"].contains($0.category) }
            var attempted = Set<String>()
            for item in featured + Array(result.items.prefix(120)) {
                guard coverCache.count < 120, let id = item.resourceID, attempted.insert(id).inserted else { continue }
                let rows = try catalog.rows("SELECT i.Image FROM Images i JOIN Records r ON r.RecordId = i.RecordId WHERE r.ResourceId = ? AND length(i.Image) <= 250000 LIMIT 1", [id])
                if let cover = rows.first?["Image"] as? Data { coverCache[id] = cover }
            }
            for index in result.items.indices {
                if let id = result.items[index].resourceID { result.items[index].cover = coverCache[id] }
            }
            result.messages.insert("Read \(books.count) books from \(data.path).", at: 0)
        } catch { result.messages.append(error.localizedDescription) }
        return result
    }
    static func layoutCommand(_ title: String) -> String {
        let title = title.trimmingCharacters(in: .whitespacesAndNewlines)
        return "open \(title)" + (title.lowercased().hasSuffix(" layout") ? "" : " layout")
    }
    private static func plans(_ documents: URL, books: [String: LibraryItem]) throws -> [LibraryItem] {
        let db = try ReadOnlyDatabase(documents.appendingPathComponent("Documents/ReadingPlan/ReadingPlan.db"))
        let docs = try db.rows("SELECT Title, ScheduleId, Sessions FROM ReadingPlanDocuments WHERE IsDeleted = 0")
        let statuses = try db.rows("SELECT SyncId, ReadSessions, SessionsMetadata, coalesce(IsArchived,0) AS Archived, NotificationTime FROM ReadingPlanStatus WHERE IsDeleted = 0")
        var output: [LibraryItem] = []
        for doc in docs {
            // .NET GUID byte order: reverse the first 4, 2 and 2 bytes.
            let bytes = [UInt8](doc["ScheduleId"] as? Data ?? Data())
            guard bytes.count == 16 else { continue }
            let order = [3,2,1,0,5,4,7,6,8,9,10,11,12,13,14,15]
            let guid = order.map { String(format: "%02x", bytes[$0]) }.joined()
            let status = statuses.first { $0.text("SyncId").replacingOccurrences(of: "-", with: "").lowercased() == guid }
            guard status?.number("Archived") != 1,
                  let sessionsData = doc.text("Sessions").data(using: .utf8),
                  let sessions = try JSONSerialization.jsonObject(with: sessionsData) as? [[String: Any]] else { continue }
            var done = Set<Int>()
            for part in (status?.text("ReadSessions") ?? "").split(separator: ",") {
                let bounds = part.split(separator: "-").compactMap { Int($0) }
                if let first = bounds.first, let last = bounds.last, first >= 0, last >= first, last < sessions.count {
                    done.formUnion(first...last)
                }
            }
            guard let next = sessions.indices.first(where: { !done.contains($0) }) else { continue }
            let session = sessions[next]
            let groups = session["readings"] as? [[[String: Any]]] ?? []
            for (index, reading) in groups.flatMap({ $0 }).enumerated() {
                guard let resource = reading["resourceId"] as? String, let book = books[resource] else { continue }
                var url = book.url
                if let reference = reading["reference"] as? String { url += ";ref=\(encoded(reference))" }
                var item = LibraryItem(id: "plan:\(guid):\(index)", title: doc.text("Title"),
                                       subtitle: "\(session["title"] as? String ?? book.title) · session \(next + 1)/\(sessions.count)",
                                       url: url, category: "plan")
                item.progress = Double(done.count) / Double(max(1, sessions.count))
                item.dueDate = session["date"] as? String
                item.reminder = status?.text("NotificationTime")
                item.resourceID = resource
                item.planKind = (item.dueDate ?? "").hasPrefix("1900") || (item.dueDate ?? "").isEmpty ? "anytime" : "today"
                item.streak = ReadingDetails.streak(status?.text("SessionsMetadata") ?? "")
                item.minutes = ReadingDetails.minutes(groups.flatMap { $0 })
                item.daysBehind = ReadingDetails.daysBehind(item.dueDate ?? "")
                output.append(item)
            }
        }
        return output
    }
}
#endif
