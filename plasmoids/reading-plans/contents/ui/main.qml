import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.components as PlasmaComponents
import org.kde.plasma.extras as PlasmaExtras
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: root

    property var plans: []
    property bool loading: false
    property string error: ""
    property string tab: "today"

    readonly property var todayPlans: plans.filter(p => p.kind === "today")
    readonly property var anytimePlans: plans.filter(p => p.kind !== "today")
    readonly property var shownPlans: (tab === "today" ? todayPlans : anytimePlans)
                                      .slice(0, Plasmoid.configuration.maxPlans)
    readonly property int dueCount: todayPlans.filter(p => p.behind !== null && p.behind >= 0).length

    function refresh() {
        loading = true
        backend.run("plans", "--reading-plans")
    }

    property alias backend: backend

    Backend {
        id: backend
        onFinished: (tag, stdout, exitCode) => {
            if (tag !== "plans")
                return
            root.loading = false
            try {
                root.plans = JSON.parse(stdout)
                root.error = ""
                if (root.todayPlans.length === 0 && root.anytimePlans.length > 0)
                    root.tab = "anytime"
            } catch (e) {
                root.error = exitCode !== 0 || !stdout
                    ? i18n("Couldn't read reading plans. Is logos-plasma installed?")
                    : i18n("Unexpected output from the backend")
            }
        }
    }

    Plasmoid.icon: "view-calendar-day"
    Plasmoid.status: dueCount > 0 ? PlasmaCore.Types.ActiveStatus : PlasmaCore.Types.PassiveStatus
    toolTipMainText: i18n("Logos Reading Plans")
    toolTipSubText: dueCount > 0 ? i18np("%1 plan has a reading due", "%1 plans have readings due", dueCount)
                                 : i18n("Nothing due")

    Plasmoid.contextualActions: [
        PlasmaCore.Action {
            text: i18n("Refresh")
            icon.name: "view-refresh"
            onTriggered: root.refresh()
        },
        PlasmaCore.Action {
            text: i18n("Show Logos")
            icon.name: "logos-plasma"
            onTriggered: backend.run("focus", "--focus")
        }
    ]

    onExpandedChanged: if (expanded) refresh()

    compactRepresentation: MouseArea {
        hoverEnabled: true
        onClicked: root.expanded = !root.expanded
        Kirigami.Icon {
            anchors.fill: parent
            source: "view-calendar-day"
            active: parent.containsMouse
        }
        PlasmaComponents.Label {
            visible: root.dueCount > 0
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            text: root.dueCount
            font.bold: true
            font.pixelSize: Math.max(Kirigami.Theme.smallFont.pixelSize, parent.height / 3)
            color: Kirigami.Theme.highlightedTextColor
            leftPadding: 3; rightPadding: 3
            background: Rectangle { color: Kirigami.Theme.highlightColor; radius: height / 2 }
        }
    }

    fullRepresentation: FullView {
        widget: root
    }

    // Logos may mark readings done at any time; refresh every 10 minutes.
    Timer {
        interval: 10 * 60 * 1000
        running: true
        repeat: true
        onTriggered: root.refresh()
    }

    Component.onCompleted: refresh()
}
