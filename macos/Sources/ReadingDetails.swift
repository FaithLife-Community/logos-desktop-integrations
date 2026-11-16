#if LOGOS_LOCAL_DATA
import Foundation

enum ReadingDetails {
    // Same public Bible chapter/verse counts and rates used by the Plasma backend.
    static let books: [Int: String] = [1: "Genesis", 2: "Exodus", 3: "Leviticus", 4: "Numbers", 5: "Deuteronomy", 6: "Joshua", 7: "Judges", 8: "Ruth", 9: "1 Samuel", 10: "2 Samuel", 11: "1 Kings", 12: "2 Kings", 13: "1 Chronicles", 14: "2 Chronicles", 15: "Ezra", 16: "Nehemiah", 17: "Esther", 18: "Job", 19: "Psalm", 20: "Proverbs", 21: "Ecclesiastes", 22: "Song of Songs", 23: "Isaiah", 24: "Jeremiah", 25: "Lamentations", 26: "Ezekiel", 27: "Daniel", 28: "Hosea", 29: "Joel", 30: "Amos", 31: "Obadiah", 32: "Jonah", 33: "Micah", 34: "Nahum", 35: "Habakkuk", 36: "Zephaniah", 37: "Haggai", 38: "Zechariah", 39: "Malachi", 61: "Matthew", 62: "Mark", 63: "Luke", 64: "John", 65: "Acts", 66: "Romans", 67: "1 Corinthians", 68: "2 Corinthians", 69: "Galatians", 70: "Ephesians", 71: "Philippians", 72: "Colossians", 73: "1 Thessalonians", 74: "2 Thessalonians", 75: "1 Timothy", 76: "2 Timothy", 77: "Titus", 78: "Philemon", 79: "Hebrews", 80: "James", 81: "1 Peter", 82: "2 Peter", 83: "1 John", 84: "2 John", 85: "3 John", 86: "Jude", 87: "Revelation"]
    private static let verseTable = "31,25,24,26,32,22,24,22,29,32,32,20,18,24,21,16,27,33,38,18,34,24,20,67,34,35,46,22,35,43,55,32,20,31,29,43,36,30,23,23,57,38,34,34,28,34,31,22,33,26;22,25,22,31,23,30,25,32,35,29,10,51,22,31,27,36,16,27,25,26,36,31,33,18,40,37,21,43,46,38,18,35,23,35,35,38,29,31,43,38;17,16,17,35,19,30,38,36,24,20,47,8,59,57,33,34,16,30,37,27,24,33,44,23,55,46,34;54,34,51,49,31,27,89,26,23,36,35,16,33,45,41,50,13,32,22,29,35,41,30,25,18,65,23,31,40,16,54,42,56,29,34,13;46,37,29,49,33,25,26,20,29,22,32,32,18,29,23,22,20,22,21,20,23,30,25,22,19,19,26,68,29,20,30,52,29,12;18,24,17,24,15,27,26,35,27,43,23,24,33,15,63,10,18,28,51,9,45,34,16,33;36,23,31,24,31,40,25,35,57,18,40,15,25,20,20,31,13,31,30,48,25;22,23,18,22;28,36,21,22,12,21,17,22,27,27,15,25,23,52,35,23,58,30,24,42,15,23,29,22,44,25,12,25,11,31,13;27,32,39,12,25,23,29,18,13,19,27,31,39,33,37,23,29,33,43,26,22,51,39,25;53,46,28,34,18,38,51,66,28,29,43,33,34,31,34,34,24,46,21,43,29,53;18,25,27,44,27,33,20,29,37,36,21,21,25,29,38,20,41,37,37,21,26,20,37,20,30;54,55,24,43,26,81,40,40,44,14,47,40,14,17,29,43,27,17,19,8,30,19,32,31,31,32,34,21,30;17,18,17,22,14,42,22,18,31,19,23,16,22,15,19,14,19,34,11,37,20,12,21,27,28,23,9,27,36,27,21,33,25,33,27,23;11,70,13,24,17,22,28,36,15,44;11,20,32,23,19,19,73,18,38,39,36,47,31;22,23,15,17,14,14,10,17,32,3;22,13,26,21,27,30,21,22,35,22,20,25,28,22,35,22,16,21,29,29,34,30,17,25,6,14,23,28,25,31,40,22,33,37,16,33,24,41,30,24,34,17;6,12,8,8,12,10,17,9,20,18,7,8,6,7,5,11,15,50,14,9,13,31,6,10,22,12,14,9,11,12,24,11,22,22,28,12,40,22,13,17,13,11,5,26,17,11,9,14,20,23,19,9,6,7,23,13,11,11,17,12,8,12,11,10,13,20,7,35,36,5,24,20,28,23,10,12,20,72,13,19,16,8,18,12,13,17,7,18,52,17,16,15,5,23,11,13,12,9,9,5,8,28,22,35,45,48,43,13,31,7,10,10,9,8,18,19,2,29,176,7,8,9,4,8,5,6,5,6,8,8,3,18,3,3,21,26,9,8,24,13,10,7,12,15,21,10,20,14,9,6;33,22,35,27,23,35,27,36,18,32,31,28,25,35,33,33,28,24,29,30,31,29,35,34,28,28,27,28,27,33,31;18,26,22,16,20,12,29,17,18,20,10,14;17,17,11,16,16,13,13,14;31,22,26,6,30,13,25,22,21,34,16,6,22,32,9,14,14,7,25,6,17,25,18,23,12,21,13,29,24,33,9,20,24,17,10,22,38,22,8,31,29,25,28,28,25,13,15,22,26,11,23,15,12,17,13,12,21,14,21,22,11,12,19,12,25,24;19,37,25,31,31,30,34,22,26,25,23,17,27,22,21,21,27,23,15,18,14,30,40,10,38,24,22,17,32,24,40,44,26,22,19,32,21,28,18,16,18,22,13,30,5,28,7,47,39,46,64,34;22,22,66,22,22;28,10,27,17,17,14,27,18,11,22,25,28,23,23,8,63,24,32,14,49,32,31,49,27,17,21,36,26,21,26,18,32,33,31,15,38,28,23,29,49,26,20,27,31,25,24,23,35;21,49,30,37,31,28,28,27,27,21,45,13;11,23,5,19,15,11,16,14,17,15,12,14,16,9;20,32,21;15,16,15,13,27,14,17,14,15;21;17,10,10,11;16,13,12,13,15,16,20;15,13,19;17,20,19;18,15,20;15,23;21,13,10,14,11,15,14,23,17,12,17,14,9,21;14,17,18,6;25,23,17,25,48,34,29,34,38,42,30,50,58,36,39,28,27,35,30,34,46,46,39,51,46,75,66,20;45,28,35,41,43,56,37,38,50,52,33,44,37,72,47,20;80,52,38,44,39,49,50,56,62,42,54,59,35,35,32,31,37,43,48,47,38,71,56,53;51,25,36,54,47,71,53,59,41,42,57,50,38,31,27,33,26,40,42,31,25;26,47,26,37,42,15,60,40,43,48,30,25,52,28,41,40,34,28,41,38,40,30,35,27,27,32,44,31;32,29,31,25,21,23,25,39,33,21,36,21,14,23,33,27;31,16,23,21,13,20,40,13,27,33,34,31,13,40,58,24;24,17,18,18,21,18,16,24,15,18,33,21,14;24,21,29,31,26,18;23,22,21,32,33,24;30,30,21,23;29,23,25,18;10,20,13,18,28;12,17,18;20,15,16,16,25,21;18,26,17,22;16,15,15;25;14,18,19,16,14,20,28,13,28,39,40,29,25;27,26,18,17,20;25,25,22,19,14;21,22,18;10,29,24,21,21;13;14;25;20,29,22,11,14,17,17,13,21,11,19,17,18,20,8,21,18,24,21,15,27,21".split(separator: ";").map { $0.split(separator: ",").compactMap { Int($0) } }
    private static func date(_ value: String) -> Date? {
        let formatter = DateFormatter(); formatter.dateFormat = "yyyy-MM-dd"
        return formatter.date(from: String(value.prefix(10)))
    }
    static func daysBehind(_ value: String) -> Int? {
        guard !value.hasPrefix("1900"), let due = date(value) else { return nil }
        return Calendar.current.dateComponents([.day], from: due, to: Calendar.current.startOfDay(for: Date())).day
    }
    static func streak(_ metadata: String) -> Int {
        guard let data = metadata.data(using: .utf8),
              let values = (try? JSONSerialization.jsonObject(with: data)) as? [String: [String: Any]] else { return 0 }
        let days = Set(values.values.compactMap { ($0["completedDate"] as? String).flatMap(date) })
        let calendar = Calendar.current
        var day = calendar.startOfDay(for: Date())
        if !days.contains(day) { day = calendar.date(byAdding: .day, value: -1, to: day)! }
        var count = 0
        while days.contains(day) {
            count += 1
            day = calendar.date(byAdding: .day, value: -1, to: day)!
        }
        return count
    }
    static func referenceParts(_ reference: String) -> [[Int]] {
        guard let dot = reference.firstIndex(of: ".") else { return [] }
        return reference[reference.index(after: dot)...].split(separator: "-").map { $0.split(separator: ".").compactMap { Int($0) } }
    }
    static func verseCount(_ reference: String) -> Int? {
        let parts = referenceParts(reference)
        guard let start = parts.first, let end = parts.last, let firstBook = start.first, let lastBook = end.first, lastBook >= firstBook else { return nil }
        var count = 0
        for book in firstBook...lastBook {
            let index = book <= 39 ? book - 1 : book - 61 + 39
            guard (1...39).contains(book) || (61...87).contains(book), verseTable.indices.contains(index) else { return nil }
            let verses = verseTable[index]
            let firstChapter = book == firstBook && start.count > 1 ? start[1] : 1
            let lastChapter = book == lastBook && end.count > 1 ? end[1] : verses.count
            guard firstChapter > 0, lastChapter >= firstChapter, lastChapter <= verses.count else { return nil }
            for chapter in firstChapter...lastChapter {
                let firstVerse = book == firstBook && start.count > 2 && chapter == start[1] ? start[2] : 1
                let lastVerse = book == lastBook && end.count > 2 && chapter == end[1] ? end[2] : verses[chapter - 1]
                count += max(0, lastVerse - firstVerse + 1)
            }
        }
        return count
    }
    static func minutes(_ readings: [[String: Any]]) -> Int? {
        var total = 0.0
        for reading in readings {
            if let reference = reading["reference"] as? String, let verses = verseCount(reference) { total += Double(verses) / 10.4 }
            else if let range = reading["textRange"] as? String, let positions = textPositions(range) { total += Double(positions) / 1475 }
            else { return nil }
        }
        return total > 0 ? max(1, Int(total.rounded())) : nil
    }
    private static func textPositions(_ raw: String) -> Int? {
        let text = raw.removingPercentEncoding?.removingPercentEncoding ?? raw
        if let range = text.range(of: #"\?len=(\d+)"#, options: .regularExpression) { return Int(text[range].dropFirst(5)) }
        func position(_ prefix: String) -> (String, Int, Int)? {
            let pattern = prefix + #"Position=Article=([^|]+)\|ArticleLength=(\d+)\|.*?Offset=(\d+)"#
            guard let regex = try? NSRegularExpression(pattern: pattern),
                  let match = regex.firstMatch(in: text, range: NSRange(text.startIndex..., in: text)) else { return nil }
            let parts = (1...3).compactMap { Range(match.range(at: $0), in: text).map { String(text[$0]) } }
            guard parts.count == 3, let length = Int(parts[1]), let offset = Int(parts[2]) else { return nil }
            return (parts[0], length, offset)
        }
        guard let start = position("Start"), let end = position("End") else { return nil }
        if start.0 == end.0 { return max(0, end.2 - start.2) }
        // We cannot measure intervening articles without opening protected resources.
        return nil
    }
    static func readable(_ reference: String) -> String {
        let parts = referenceParts(reference)
        guard let start = parts.first, let book = start.first, let name = books[book] else { return reference }
        let begin = name + (start.count > 1 ? " " + start.dropFirst().map(String.init).joined(separator: ":") : "")
        guard parts.count > 1, let end = parts.last, let endBook = end.first else { return begin }
        if endBook != book { return begin + "–" + (books[endBook] ?? "") + " " + end.dropFirst().map(String.init).joined(separator: ":") }
        if start.count == 3 && end.count == 3 && start[1] == end[1] { return begin + "–" + String(end[2]) }
        return begin + "–" + end.dropFirst().map(String.init).joined(separator: ":")
    }
}
#endif
