import Foundation

struct RunnerAction: Identifiable {
    var id: String { title + value }
    var title: String
    var detail: String = ""
    var value: String
    var isURL = false
    var isCopy = false
}

enum Runner {
    static let help = "o passage · s words · 'phrase · .words · fb topic · ws word · ol book · lay layout · cv passage · cmd exact command"
    static func actions(_ query: String, items: [LibraryItem]) -> [RunnerAction] {
        let query = query.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !query.isEmpty else { return [] }
        let parts = query.split(maxSplits: 1, whereSeparator: \.isWhitespace)
        let alias = String(parts[0]).lowercased()
        let argument = parts.count > 1 ? String(parts[1]) : ""
        func command(_ title: String, _ value: String) -> [RunnerAction] {
            [RunnerAction(title: title, detail: value, value: value)]
        }
        func matches(_ categories: [String], fallback: String? = nil) -> [RunnerAction] {
            let words = argument.lowercased().split(separator: " ")
            let results = items.filter { item in
                categories.contains(item.category) && words.allSatisfy {
                    (item.title + " " + item.subtitle + " " + (item.abbreviation ?? "")).lowercased().contains($0)
                }
            }.prefix(15).map { RunnerAction(title: $0.title, detail: $0.subtitle, value: $0.url, isURL: true) }
            if results.isEmpty, let fallback, !argument.isEmpty { return command(argument, fallback) }
            return results
        }
        let bibles = items.filter { $0.kind == "text.monograph.bible" }.sorted {
            let a = $0.priority ?? Int.max, b = $1.priority ?? Int.max
            return a == b ? ($0.uses ?? 0) > ($1.uses ?? 0) : a < b
        }
        func biblePicker(search: Bool) -> [RunnerAction] {
            var results: [RunnerAction] = search ? [RunnerAction(title: "Search Top Bibles", value: "search for \(argument)")] : []
            results += bibles.prefix(6).map { bible in
                if search { return RunnerAction(title: "Search \(bible.abbreviation ?? bible.title)", value: "search \(bible.abbreviation ?? bible.title) for \(argument)") }
                return RunnerAction(title: bible.title, detail: argument, value: bible.url + ";ref=Bible.\(encode(argument))", isURL: true)
            }
            return results.isEmpty ? command("Open \(argument)", "open \(argument)") : results
        }
        switch alias {
        case "cmd": return argument.isEmpty ? [] : command("Run Logos command", argument)
        case "o", "open": return argument.isEmpty ? [] : biblePicker(search: false)
        case "s", "search": return argument.isEmpty ? [] : biblePicker(search: true)
        case "stb": return argument.isEmpty ? [] : command("Search Top Bibles", "search for \(argument)")
        case "sll": return argument.isEmpty ? [] : command("Search library", "search all for \(argument)")
        case "fb", "factbook": return matches(["factbook"], fallback: "open Factbook to \(argument)")
        case "ws", "obws": return argument.isEmpty ? [] : command("Bible Word Study: \(argument)", "open Bible Word Study to \(argument)")
        case "opg": return command("Passage Guide", argument.isEmpty ? "open Passage Guide" : "open Passage Guide to \(argument)")
        case "oeg": return command("Exegetical Guide", argument.isEmpty ? "open Exegetical Guide" : "open Exegetical Guide to \(argument)")
        case "otc", "ltc", "ltcs": return command("Text Comparison", argument.isEmpty ? "open Text Comparison" : "open Text Comparison to \(argument)")
        case "oh": return command("Harmony", "open Harmony")
        case "ol", "library": return matches(["book", "devotional"], fallback: "open \(argument)")
        case "lex":
            guard !argument.isEmpty else { return [] }
            let language = argument.unicodeScalars.contains { (0x0590...0x05ff).contains($0.value) } ? "h" :
                (argument.unicodeScalars.contains { (0x0370...0x03ff).contains($0.value) || (0x1f00...0x1fff).contains($0.value) } ? "g" : "")
            let lexicons = items.filter { ($0.kind ?? "").hasPrefix("text.monograph.lexicon") &&
                (language.isEmpty || ($0.language ?? "").isEmpty || ($0.language ?? "").contains(language)) }.sorted {
                    ($0.priority ?? Int.max) < ($1.priority ?? Int.max)
                }
            let results = lexicons.prefix(6).map { RunnerAction(title: $0.title, detail: argument, value: $0.url + ";hw=\(encode(argument))", isURL: true) }
            return results.isEmpty ? command("Look up \(argument)", "look up \(argument)") : results
        case "rp": return matches(["plan"])
        case "or": return matches(["recent"])
        case "today": return matches(["devotional", "pinned"])
        case "logos", "help":
            return [RunnerAction(title: "Open a passage", detail: "o John 3:16", value: "open John 3:16"),
                    RunnerAction(title: "Factbook", detail: "fb Moses", value: "open Factbook"),
                    RunnerAction(title: "Passage Study layout", detail: "lay passage study", value: "open passage study layout"),
                    RunnerAction(title: "Passage Guide", detail: "opg John 3", value: "open Passage Guide")]
                .filter { argument.isEmpty || ($0.title + $0.detail).localizedCaseInsensitiveContains(argument) }
        case "lay", "layout":
            return matches(["layout"], fallback: "open \(argument)" + (argument.lowercased().hasSuffix(" layout") ? "" : " layout"))
        case "cv": return argument.isEmpty ? [] : [RunnerAction(title: "Copy \(argument)", value: argument, isCopy: true)]
        default:
            if query.hasPrefix("'") { return command("Exact phrase search", "search for \"\(query.dropFirst())\"") }
            if query.hasPrefix(".") { return command("Word search", "search for \(query.dropFirst())") }
            // Typed Bible aliases are available only when a catalog was compiled in and loaded.
            if alias.hasPrefix("o") || alias.hasPrefix("s") {
                let abbreviation = String(alias.dropFirst())
                if let book = items.first(where: { ($0.abbreviation ?? "").lowercased().replacingOccurrences(of: " ", with: "") == abbreviation && ["book", "devotional"].contains($0.category) }) {
                    if alias.hasPrefix("o") {
                        let value = book.url + (argument.isEmpty ? "" : ";ref=Bible.\(encode(argument))")
                        return [RunnerAction(title: book.title, detail: argument, value: value, isURL: true)]
                    }
                    return command("Search \(book.abbreviation ?? book.title)", "search \(book.abbreviation ?? book.title) for \(argument)")
                }
            }
            return command("Open \(query)", "open \(query)")
        }
    }
    static func lookupCommand(_ text: String) -> String {
        let text = text.trimmingCharacters(in: .whitespacesAndNewlines)
        if let reference = ReferenceParser.find(in: text).first { return "open \(reference)" }
        if !text.isEmpty, !text.contains(where: { $0.isWhitespace || $0.isNumber }) {
            return "open Bible Word Study to \(text)"
        }
        return "open \(text)"
    }
    private static func encode(_ text: String) -> String {
        text.addingPercentEncoding(withAllowedCharacters: .alphanumerics) ?? text
    }
}
