import AppIntents
import AppKit
import SwiftUI
import WidgetKit

struct LogosEntry: TimelineEntry {
    let date: Date
    var snapshot = IntegrationSnapshot()
    var verseImage: Data? = nil
    var verseTitle = "Verse of the Day"
    var verseURL = "logos-integrations://command?q=open%20Bible"
}

struct LogosProvider: TimelineProvider {
    func placeholder(in context: Context) -> LogosEntry {
        LogosEntry(date: Date(), snapshot: IntegrationSnapshot(items: [
            LibraryItem(id: "example", title: "Today’s reading", subtitle: "Open in Logos",
                        url: SharedStore.commandURL("open passage study layout"), category: "pinned")]))
    }
    func getSnapshot(in context: Context, completion: @escaping (LogosEntry) -> Void) {
        completion(LogosEntry(date: Date(), snapshot: SharedStore.read()))
    }
    func getTimeline(in context: Context, completion: @escaping (Timeline<LogosEntry>) -> Void) {
        let entry = LogosEntry(date: Date(), snapshot: SharedStore.read())
        completion(Timeline(entries: [entry], policy: .after(Date().addingTimeInterval(900))))
    }
}

struct VerseProvider: TimelineProvider {
    func placeholder(in context: Context) -> LogosEntry { LogosEntry(date: Date()) }
    func getSnapshot(in context: Context, completion: @escaping (LogosEntry) -> Void) { completion(LogosEntry(date: Date())) }
    func getTimeline(in context: Context, completion: @escaping (Timeline<LogosEntry>) -> Void) {
        Task {
            var entry = LogosEntry(date: Date())
            do {
                let request = URLRequest(url: URL(string: "https://biblia.com/verseoftheday")!, timeoutInterval: 20)
                let (data, _) = try await URLSession.shared.data(for: request)
                let html = String(decoding: data, as: UTF8.self)
                if let title = capture("<meta[^>]*property=[\"']og:title[\"'][^>]*content=[\"']([^\"']+)", in: html) {
                    entry.verseTitle = decode(title)
                }
                if let rawLink = capture("href=[\"'](https://ref\\.ly/logosres/[^\"']+)", in: html),
                   let parts = URLComponents(string: decode(rawLink)) {
                    let resource = parts.path.replacingOccurrences(of: "/logosres/", with: "")
                    let parameters = (parts.percentEncodedQuery ?? "").split(separator: "&").filter { !$0.hasPrefix("utm_") }
                    entry.verseURL = "logosres:" + resource + (parameters.isEmpty ? "" : ";" + parameters.joined(separator: ";"))
                }
                if let raw = capture("<meta[^>]*property=[\"']og:image[\"'][^>]*content=[\"']([^\"']+)", in: html),
                   let imageURL = URL(string: decode(raw)), imageURL.scheme == "https" {
                    let (image, _) = try await URLSession.shared.data(for: URLRequest(url: imageURL, timeoutInterval: 20))
                    if image.count < 8_000_000 { entry.verseImage = image }
                }
            } catch { entry.verseTitle = "Verse of the Day — temporarily unavailable" }
            completion(Timeline(entries: [entry], policy: .after(Date().addingTimeInterval(3600))))
        }
    }
    private func capture(_ pattern: String, in text: String, group: Int = 1) -> String? {
        guard let regex = try? NSRegularExpression(pattern: pattern, options: [.caseInsensitive]),
              let match = regex.firstMatch(in: text, range: NSRange(text.startIndex..., in: text)),
              let range = Range(match.range(at: group), in: text) else { return nil }
        return String(text[range])
    }
    private func decode(_ text: String) -> String {
        text.replacingOccurrences(of: "&amp;", with: "&").replacingOccurrences(of: "&quot;", with: "\"")
    }
}

struct ItemWidgetView: View {
    let entry: LogosEntry
    let title: String
    let categories: [String]
    @Environment(\.widgetFamily) private var family
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Label(title, systemImage: "book.closed").font(.headline)
            let items = entry.snapshot.items.filter { categories.contains($0.category) }
            if items.isEmpty {
                Text(BuildFeatures.localData ? "Use Refresh integrations in the menu bar. Shared data requires App Group signing." : "Edit this widget to choose a command.")
                    .font(.caption).foregroundStyle(.secondary)
            } else {
                ForEach(Array(items.prefix(family == .systemSmall ? 1 : 3))) { item in
                    if let url = URL(string: item.url) {
                        Link(destination: url) {
                            HStack {
                                if let data = item.cover, let image = NSImage(data: data) {
                                    Image(nsImage: image).resizable().scaledToFit().frame(width: 30, height: 40)
                                }
                                VStack(alignment: .leading, spacing: 3) {
                                    Text(item.title).font(.subheadline).lineLimit(2)
                                    Text(item.subtitle).font(.caption2).foregroundStyle(.secondary).lineLimit(1)
                                    if let progress = item.progress { ProgressView(value: progress) }
                                    if let behind = item.daysBehind, behind > 0 { Text("\(behind) days overdue").font(.caption2).foregroundStyle(.red) }
                                    if let minutes = item.minutes { Text("~\(minutes) min · \(item.streak ?? 0)-day streak").font(.caption2) }
                                }
                            }
                        }
                    }
                }
            }
            Spacer(minLength: 0)
        }.containerBackground(.background, for: .widget)
    }
}

struct CommandOptions: WidgetConfigurationIntent {
    static var title: LocalizedStringResource = "Logos command"
    @Parameter(title: "Title", default: "Passage Study") var title: String
    @Parameter(title: "Logos command", default: "open passage study layout") var command: String
}
struct CommandProvider: AppIntentTimelineProvider {
    func placeholder(in context: Context) -> LogosEntry { entry(CommandOptions()) }
    func snapshot(for configuration: CommandOptions, in context: Context) async -> LogosEntry { entry(configuration) }
    func timeline(for configuration: CommandOptions, in context: Context) async -> Timeline<LogosEntry> {
        Timeline(entries: [entry(configuration)], policy: .never)
    }
    private func entry(_ configuration: CommandOptions) -> LogosEntry {
        LogosEntry(date: Date(), snapshot: IntegrationSnapshot(items: [
            LibraryItem(id: "command", title: configuration.title, subtitle: "Open in Logos",
                        url: SharedStore.commandURL(configuration.command), category: "pinned")]))
    }
}
struct ShortcutsWidget: Widget {
    var body: some WidgetConfiguration {
        AppIntentConfiguration(kind: "LogosShortcuts", intent: CommandOptions.self, provider: CommandProvider()) {
            ItemWidgetView(entry: $0, title: "Logos", categories: ["pinned"])
        }.configurationDisplayName("Logos command")
            .description("Open your devotional, layout or any Logos command. Edit this widget to choose.")
            .supportedFamilies([.systemSmall, .systemMedium])
    }
}
#if LOGOS_LOCAL_DATA
enum PlanPeriod: String, AppEnum {
    case today, anytime
    static var typeDisplayRepresentation: TypeDisplayRepresentation = "Plans"
    static var caseDisplayRepresentations: [PlanPeriod: DisplayRepresentation] = [.today: "Today", .anytime: "Anytime"]
}
struct PlanOptions: WidgetConfigurationIntent {
    static var title: LocalizedStringResource = "Reading plans"
    @Parameter(title: "Show", default: .today) var period: PlanPeriod
}
struct PlanProvider: AppIntentTimelineProvider {
    func placeholder(in context: Context) -> LogosEntry { LogosEntry(date: Date()) }
    func snapshot(for configuration: PlanOptions, in context: Context) async -> LogosEntry { entry(configuration) }
    func timeline(for configuration: PlanOptions, in context: Context) async -> Timeline<LogosEntry> {
        Timeline(entries: [entry(configuration)], policy: .after(Date().addingTimeInterval(900)))
    }
    private func entry(_ configuration: PlanOptions) -> LogosEntry {
        var snapshot = SharedStore.read()
        snapshot.items = snapshot.items.filter { $0.category == "devotional" || ($0.category == "plan" && $0.planKind == configuration.period.rawValue) }
        return LogosEntry(date: Date(), snapshot: snapshot)
    }
}
struct ReadingPlansWidget: Widget {
    var body: some WidgetConfiguration {
        AppIntentConfiguration(kind: "LogosReadingPlans", intent: PlanOptions.self, provider: PlanProvider()) {
            ItemWidgetView(entry: $0, title: "Today in Logos", categories: ["plan", "devotional"])
        }.configurationDisplayName("Logos reading plans")
            .description("Next readings, progress and devotionals.")
            .supportedFamilies([.systemSmall, .systemMedium, .systemLarge])
    }
}
struct SermonWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: "LogosSermonCommentaries", provider: LogosProvider()) {
            ItemWidgetView(entry: $0, title: "For your sermon", categories: ["commentary"])
        }.configurationDisplayName("Logos sermon commentaries")
            .description("Your highly rated commentaries at your next sermon passage.")
            .supportedFamilies([.systemSmall, .systemMedium, .systemLarge])
    }
}
enum ShowcaseMode: String, AppEnum {
    case unread, sermon, both
    static var typeDisplayRepresentation: TypeDisplayRepresentation = "Showcase"
    static var caseDisplayRepresentations: [ShowcaseMode: DisplayRepresentation] = [.unread: "Unread books", .sermon: "Sermon commentaries", .both: "Both"]
}
struct ShowcaseOptions: WidgetConfigurationIntent {
    static var title: LocalizedStringResource = "Showcase"
    @Parameter(title: "Show", default: .unread) var mode: ShowcaseMode
}
struct ShowcaseProvider: AppIntentTimelineProvider {
    func placeholder(in context: Context) -> LogosEntry { LogosEntry(date: Date()) }
    func snapshot(for configuration: ShowcaseOptions, in context: Context) async -> LogosEntry { entry(configuration) }
    func timeline(for configuration: ShowcaseOptions, in context: Context) async -> Timeline<LogosEntry> {
        Timeline(entries: [entry(configuration)], policy: .after(Date().addingTimeInterval(900)))
    }
    private func entry(_ configuration: ShowcaseOptions) -> LogosEntry {
        var snapshot = SharedStore.read()
        let unread = snapshot.items.filter { $0.category == "showcase" }
        let sermon = snapshot.items.filter { $0.category == "commentary" }
        switch configuration.mode {
        case .unread: snapshot.items = unread
        case .sermon: snapshot.items = sermon
        case .both:
            snapshot.items = (0..<max(unread.count, sermon.count)).flatMap { index -> [LibraryItem] in
                (index < unread.count ? [unread[index]] : []) + (index < sermon.count ? [sermon[index]] : [])
            }
        }
        return LogosEntry(date: Date(), snapshot: snapshot)
    }
}
struct ShowcaseWidget: Widget {
    var body: some WidgetConfiguration {
        AppIntentConfiguration(kind: "LogosShowcase", intent: ShowcaseOptions.self, provider: ShowcaseProvider()) {
            ItemWidgetView(entry: $0, title: "From your library", categories: ["showcase", "commentary"])
        }.configurationDisplayName("Logos showcase")
            .description("Well-rated unread books from your library.")
            .supportedFamilies([.systemSmall, .systemMedium, .systemLarge])
    }
}
#endif
struct VerseWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: "LogosVerseOfTheDay", provider: VerseProvider()) { entry in
            VStack {
                if let data = entry.verseImage, let image = NSImage(data: data) {
                    Image(nsImage: image).resizable().scaledToFit()
                } else { Image(systemName: "book").font(.largeTitle) }
                Text(entry.verseTitle).font(.caption).lineLimit(2)
            }.containerBackground(.background, for: .widget)
                .widgetURL(URL(string: entry.verseURL))
        }.configurationDisplayName("Logos Verse of the Day")
            .description("Daily verse art from Biblia.com. Opens in Logos.")
            .supportedFamilies([.systemSmall, .systemMedium, .systemLarge])
    }
}

@main
struct LogosWidgets: WidgetBundle {
    var body: some Widget {
        ShortcutsWidget()
        VerseWidget()
        #if LOGOS_LOCAL_DATA
        ReadingPlansWidget()
        ShowcaseWidget()
        SermonWidget()
        #endif
    }
}
