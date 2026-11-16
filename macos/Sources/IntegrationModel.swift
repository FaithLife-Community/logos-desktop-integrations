import AppKit
import CoreSpotlight
import UniformTypeIdentifiers
import UserNotifications
import WidgetKit

@MainActor
final class IntegrationModel: NSObject, ObservableObject, UNUserNotificationCenterDelegate {
    @Published var items: [LibraryItem] = []
    @Published var status = "Ready"
    @Published var busy = false
    private var refreshTask: Task<Void, Never>?
    private var pollingTask: Task<Void, Never>?
    func startRefreshing() {
        guard pollingTask == nil else { return }
        refresh()
        // The menu-bar app stays alive when its window closes. Keep refreshing then too.
        pollingTask = Task { [weak self] in
            while !Task.isCancelled {
                do { try await Task.sleep(nanoseconds: 300_000_000_000) }
                catch { return }
                guard let self else { return }
                self.refresh()
            }
        }
    }
    override init() {
        super.init()
        UserDefaults.standard.register(defaults: ["spotlightEnabled": true])
        UNUserNotificationCenter.current().delegate = self
    }
    func execute(_ action: RunnerAction) {
        guard !busy else { return }
        busy = true
        Task {
            defer { busy = false }
            do {
                if action.isCopy {
                    _ = try LogosAutomation.copyVerses(action.value)
                    status = "Verses copied to clipboard."
                } else if action.isURL {
                    try await LogosAutomation.open(action.value)
                    status = "Opened \(action.title)."
                } else {
                    try await LogosAutomation.command(action.value)
                    status = "Sent to Logos: \(action.value)"
                }
            } catch { status = error.localizedDescription }
        }
    }
    func refresh() {
        guard refreshTask == nil else { return }
        status = "Refreshing…"
        refreshTask = Task {
            defer { refreshTask = nil }
            #if LOGOS_LOCAL_DATA
            let root = UserDefaults.standard.string(forKey: "logosDataRoot") ?? ""
            let result = await Task.detached(priority: .utility) { LocalLogosData.read(root: root) }.value
            items = result.items
            status = result.messages.joined(separator: "\n")
            await updateIndex()
            await scheduleReminders()
            #else
            items = []
            status = "Commands-only build: access to the Logos folder is compiled out."
            await removeIndex()
            let pending = await UNUserNotificationCenter.current().pendingNotificationRequests()
            UNUserNotificationCenter.current().removePendingNotificationRequests(withIdentifiers: pending.map(\.identifier).filter { $0.hasPrefix("plan:") })
            #endif
            publishSnapshot()
        }
    }
    private func publishSnapshot() {
        SearchCache.write(items)
        let forWidgets = items.filter { ["plan", "devotional", "showcase", "commentary"].contains($0.category) }
        do {
            try SharedStore.write(IntegrationSnapshot(items: forWidgets, message: status))
            WidgetCenter.shared.reloadAllTimelines()
        } catch { status += "\nWidget cache: \(error.localizedDescription)" }
    }
    private func removeIndex() async {
        try? await CSSearchableIndex(name: "LogosDesktopIntegrations").deleteAllSearchableItems()
    }
    #if LOGOS_LOCAL_DATA
    private func updateIndex() async {
        let index = CSSearchableIndex(name: "LogosDesktopIntegrations")
        if !UserDefaults.standard.bool(forKey: "spotlightEnabled") {
            try? await index.deleteAllSearchableItems()
            return
        }
        let entries = items.filter { ["book", "devotional", "layout"].contains($0.category) }.map { item in
            let attributes = CSSearchableItemAttributeSet(contentType: .item)
            attributes.title = item.title
            attributes.contentDescription = item.subtitle
            attributes.keywords = ["Logos", item.abbreviation ?? "", item.category]
            attributes.relatedUniqueIdentifier = item.url
            attributes.thumbnailData = item.cover
            return CSSearchableItem(uniqueIdentifier: item.url, domainIdentifier: "LogosDesktopIntegrations", attributeSet: attributes)
        }
        do {
            try await index.deleteAllSearchableItems()
            try await index.indexSearchableItems(entries)
        } catch { status += "\nSpotlight: \(error.localizedDescription)" }
    }
    private func scheduleReminders() async {
        let center = UNUserNotificationCenter.current()
        let existing = await center.pendingNotificationRequests()
        center.removePendingNotificationRequests(withIdentifiers: existing.map(\.identifier).filter { $0.hasPrefix("plan:") })
        guard UserDefaults.standard.bool(forKey: "remindersEnabled") else { return }
        let permission = try? await center.requestAuthorization(options: [.alert, .sound])
        guard permission == true else { return }
        let action = UNNotificationAction(identifier: "READ_NOW", title: "Read now", options: [.foreground])
        center.setNotificationCategories([UNNotificationCategory(identifier: "READING", actions: [action], intentIdentifiers: [])])
        var seen = Set<String>()
        for item in items where item.category == "plan" {
            let planID = item.id.components(separatedBy: ":").prefix(2).joined(separator: ":")
            guard seen.insert(planID).inserted, let time = item.reminder, !time.isEmpty else { continue }
            let parts = time.split(separator: ":").compactMap { Int($0) }
            guard parts.count >= 2, (0...23).contains(parts[0]), (0...59).contains(parts[1]) else { continue }
            let date = item.dueDate ?? ""
            let today = DateFormatter()
            today.dateFormat = "yyyy-MM-dd"
            let due = today.date(from: String(date.prefix(10)))
            // Self-paced dates use 1900; don't notify about future sessions early.
            if let due, due > Calendar.current.startOfDay(for: Date()) { continue }
            let content = UNMutableNotificationContent()
            content.title = item.title
            content.body = item.subtitle
            content.categoryIdentifier = "READING"
            content.userInfo = ["url": item.url]
            var components = DateComponents()
            components.hour = parts[0]; components.minute = parts[1]
            let request = UNNotificationRequest(identifier: planID, content: content,
                trigger: UNCalendarNotificationTrigger(dateMatching: components, repeats: true))
            try? await center.add(request)
        }
    }
    #endif
    nonisolated func userNotificationCenter(_ center: UNUserNotificationCenter, didReceive response: UNNotificationResponse,
                                            withCompletionHandler completionHandler: @escaping () -> Void) {
        if let url = response.notification.request.content.userInfo["url"] as? String {
            Task { @MainActor in try? await LogosAutomation.open(url) }
        }
        completionHandler()
    }
    nonisolated func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification,
                                            withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void) {
        completionHandler([.banner, .sound])
    }
}
