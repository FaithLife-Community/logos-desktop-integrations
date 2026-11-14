import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.components as PlasmaComponents
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: root

    readonly property var cfg: Plasmoid.configuration
    property bool loading: false
    property string error: ""

    // The "Read in Logos" link on biblia.com, converted: logosres:LLS:1.0.710;ref=BibleESV.Ro6.4
    readonly property string logosRef: {
        const m = /ref=([^;]+)/.exec(cfg.lastLogosUrl)
        return m ? m[1] : ""
    }

    function targetUrl() {
        switch (cfg.clickAction) {
        case "passageGuide":
            return "logos4:Guide;t=Passage%20Guide;ref=" + logosRef
        case "exegeticalGuide":
            return "logos4:Guide;t=Exegetical%20Guide;ref=" + logosRef
        case "layout":
            return "layout:" + cfg.layout
        case "custom":
            return cfg.customUrl.replace("{ref}", logosRef)
        default:
            return cfg.bible ? "logosres:" + cfg.bible + ";ref=" + logosRef : cfg.lastLogosUrl
        }
    }

    function openInLogos() {
        if (logosRef || cfg.clickAction === "layout")
            backend.openUrl(targetUrl())
    }

    function decodeEntities(s) {
        return s.replace(/&amp;/g, "&").replace(/&quot;/g, '"').replace(/&#0?39;|&#x27;|&apos;/g, "'")
                .replace(/&lt;/g, "<").replace(/&gt;/g, ">")
                .replace(/&#(\d+);/g, (m, n) => String.fromCharCode(parseInt(n, 10)))
    }

    function meta(html, prop) {
        let m = new RegExp('<meta[^>]+(?:property|name)="' + prop + '"[^>]*content="([^"]*)"', "i").exec(html)
        if (!m)
            m = new RegExp('<meta[^>]+content="([^"]*)"[^>]*(?:property|name)="' + prop + '"', "i").exec(html)
        return m ? decodeEntities(m[1]) : ""
    }

    // https://ref.ly/logosres/LLS:1.0.710?ref=BibleESV.Ro6.4&utm_source=… → logosres:LLS:1.0.710;ref=BibleESV.Ro6.4
    function reflyToLogos(href) {
        const m = /ref\.ly\/logosres\/([^?"]+)\??([^"]*)/.exec(href)
        if (!m)
            return ""
        const params = m[2].split("&").filter(p => p && !p.startsWith("utm_"))
        return "logosres:" + m[1] + (params.length ? ";" + params.join(";") : "")
    }

    function today() {
        return Qt.formatDate(new Date(), "yyyy-MM-dd")  // local date, not UTC
    }

    function refresh() {
        loading = true
        const xhr = new XMLHttpRequest()
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== XMLHttpRequest.DONE)
                return
            loading = false
            if (xhr.status !== 200) {
                error = i18n("Couldn't reach %1 (HTTP %2)", cfg.sourceUrl, xhr.status)
                return
            }
            const html = xhr.responseText
            const image = meta(html, "og:image")
            const href = /href="(https:\/\/ref\.ly\/logosres\/[^"]+)"/.exec(html)
            if (!image || !href) {
                error = i18n("The Verse of the Day page has changed; no image or Logos link found")
                return
            }
            error = ""
            cfg.lastImage = image
            cfg.lastLogosUrl = reflyToLogos(decodeEntities(href[1]))
            cfg.lastReference = meta(html, "og:title").replace(/\s*[-|–]\s*Biblia.*$/i, "")
            cfg.lastText = meta(html, "og:description")
            cfg.lastFetchedDate = today()
        }
        xhr.open("GET", cfg.sourceUrl)
        xhr.send()
    }

    Backend { id: backend }

    toolTipMainText: i18n("Logos Verse of the Day")
    toolTipSubText: i18n("Click to open in Logos")

    Plasmoid.icon: "logos-plasma"
    Plasmoid.backgroundHints: PlasmaCore.Types.DefaultBackground | PlasmaCore.Types.ConfigurableBackground
    Plasmoid.contextualActions: [
        PlasmaCore.Action {
            text: i18n("Open in Logos")
            icon.name: "document-open"
            onTriggered: root.openInLogos()
        },
        PlasmaCore.Action {
            text: i18n("Open Passage Guide")
            icon.name: "view-list-details"
            onTriggered: backend.openUrl("logos4:Guide;t=Passage%20Guide;ref=" + root.logosRef)
        },
        PlasmaCore.Action {
            text: i18n("Open on biblia.com")
            icon.name: "internet-web-browser"
            onTriggered: Qt.openUrlExternally(root.cfg.sourceUrl)
        },
        PlasmaCore.Action {
            text: i18n("Refresh")
            icon.name: "view-refresh"
            onTriggered: root.refresh()
        }
    ]

    preferredRepresentation: Plasmoid.formFactor === PlasmaCore.Types.Planar ? fullRepresentation : compactRepresentation

    compactRepresentation: Kirigami.Icon {
        source: "logos-plasma"
        active: mouse.containsMouse
        MouseArea {
            id: mouse
            anchors.fill: parent
            hoverEnabled: true
            onClicked: root.expanded = !root.expanded
        }
    }

    fullRepresentation: Item {
        Layout.preferredWidth: Kirigami.Units.gridUnit * 24
        Layout.preferredHeight: Kirigami.Units.gridUnit * 16
        Layout.minimumWidth: Kirigami.Units.gridUnit * 8
        Layout.minimumHeight: Kirigami.Units.gridUnit * 5

        // Natural size of the picture, for cropping (sourceSize of a non-cropped copy).
        Image {
            id: probe
            source: root.cfg.lastImage
            visible: false
            asynchronous: true
        }

        Image {
            id: art
            anchors.fill: parent
            source: root.cfg.lastImage
            // Optionally crop the reference footer printed along the bottom of the art.
            sourceClipRect: root.cfg.cropFooter && probe.status === Image.Ready
                ? Qt.rect(0, 0, probe.sourceSize.width,
                          Math.round(probe.sourceSize.height * (100 - root.cfg.footerPercent) / 100))
                : Qt.rect(0, 0, 0, 0)
            fillMode: Image.PreserveAspectFit
            asynchronous: true
            cache: true
            smooth: true
            mipmap: true
        }

        PlasmaComponents.BusyIndicator {
            anchors.centerIn: parent
            visible: root.loading && art.status !== Image.Ready
            running: visible
        }

        PlasmaComponents.Label {
            anchors.centerIn: parent
            width: parent.width - Kirigami.Units.gridUnit * 2
            visible: art.status !== Image.Ready && !root.loading
            wrapMode: Text.Wrap
            horizontalAlignment: Text.AlignHCenter
            text: root.error || i18n("No Verse of the Day yet")
        }

        MouseArea {
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            acceptedButtons: Qt.LeftButton
            onClicked: root.openInLogos()
        }
    }

    // One fetch per day: when the date changes (checked every 10 minutes, no network),
    // retrying on the next check if a fetch fails.
    Timer {
        interval: 10 * 60 * 1000
        running: true
        repeat: true
        onTriggered: if (root.cfg.lastFetchedDate !== root.today() && !root.loading) root.refresh()
    }

    Component.onCompleted: if (cfg.lastFetchedDate !== today() || !cfg.lastImage) refresh()
}
