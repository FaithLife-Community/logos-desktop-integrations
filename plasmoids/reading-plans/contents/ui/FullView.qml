// The expanded view, styled after the Reading Plans card on Logos's home page.
import QtQuick
import QtQuick.Layouts
import org.kde.plasma.components as PlasmaComponents
import org.kde.plasma.extras as PlasmaExtras
import org.kde.kirigami as Kirigami

ColumnLayout {
    id: view
    required property var widget

    Layout.preferredWidth: Kirigami.Units.gridUnit * 22
    Layout.preferredHeight: Kirigami.Units.gridUnit * 26
    Layout.minimumWidth: Kirigami.Units.gridUnit * 14
    Layout.minimumHeight: Kirigami.Units.gridUnit * 12
    spacing: Kirigami.Units.largeSpacing

    // Title row
    RowLayout {
        Layout.fillWidth: true
        Layout.margins: Kirigami.Units.largeSpacing
        Kirigami.Heading {
            Layout.fillWidth: true
            level: 1
            text: i18n("Reading Plans")
            elide: Text.ElideRight
        }
        PlasmaComponents.BusyIndicator {
            visible: view.widget.loading
            running: visible
            Layout.preferredWidth: Kirigami.Units.iconSizes.small
            Layout.preferredHeight: Layout.preferredWidth
        }
        PlasmaComponents.ToolButton {
            icon.name: "view-refresh"
            onClicked: view.widget.refresh()
            PlasmaComponents.ToolTip { text: i18n("Refresh") }
        }
    }

    // Today / Anytime pills
    RowLayout {
        Layout.leftMargin: Kirigami.Units.largeSpacing
        spacing: Kirigami.Units.smallSpacing
        Repeater {
            model: [
                { key: "today", label: i18n("Today"), count: view.widget.todayPlans.length },
                { key: "anytime", label: i18n("Anytime"), count: view.widget.anytimePlans.length }
            ]
            delegate: MouseArea {
                required property var modelData
                readonly property bool selected: view.widget.tab === modelData.key
                implicitWidth: pill.implicitWidth
                implicitHeight: pill.implicitHeight
                cursorShape: Qt.PointingHandCursor
                onClicked: view.widget.tab = modelData.key
                Rectangle {
                    anchors.fill: parent
                    radius: height / 2
                    color: parent.selected ? Kirigami.Theme.highlightColor
                                           : Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g,
                                                     Kirigami.Theme.textColor.b, 0.1)
                }
                RowLayout {
                    id: pill
                    anchors.centerIn: parent
                    spacing: Kirigami.Units.smallSpacing
                    PlasmaComponents.Label {
                        Layout.leftMargin: Kirigami.Units.largeSpacing
                        Layout.topMargin: Kirigami.Units.smallSpacing
                        Layout.bottomMargin: Kirigami.Units.smallSpacing
                        text: modelData.label
                        color: parent.parent.selected ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.textColor
                    }
                    PlasmaComponents.Label {
                        Layout.rightMargin: Kirigami.Units.smallSpacing
                        text: modelData.count
                        font: Kirigami.Theme.smallFont
                        horizontalAlignment: Text.AlignHCenter
                        Layout.minimumWidth: height
                        color: parent.parent.selected ? Kirigami.Theme.highlightColor : Kirigami.Theme.textColor
                        background: Rectangle {
                            radius: height / 2
                            color: parent.parent.parent.selected ? Kirigami.Theme.highlightedTextColor
                                                                 : Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g,
                                                                           Kirigami.Theme.textColor.b, 0.15)
                        }
                    }
                }
            }
        }
    }

    // Plans
    PlasmaComponents.ScrollView {
        Layout.fillWidth: true
        Layout.fillHeight: true
        ListView {
            id: list
            model: view.widget.shownPlans
            clip: true
            delegate: PlanRow {
                required property var modelData
                width: ListView.view.width
                plan: modelData
                onOpenUrl: url => view.widget.backend.openUrl(url)
            }
            PlasmaExtras.PlaceholderMessage {
                anchors.centerIn: parent
                width: parent.width - Kirigami.Units.gridUnit * 2
                visible: list.count === 0 && !view.widget.loading
                iconName: "view-calendar-day"
                text: view.widget.error || (view.widget.tab === "today" ? i18n("Nothing scheduled for today")
                                                          : i18n("No anytime plans"))
            }
        }
    }

    PlasmaComponents.Label {
        Layout.alignment: Qt.AlignRight
        Layout.margins: Kirigami.Units.largeSpacing
        text: i18n("Manage your plans")
        color: Kirigami.Theme.linkColor
        font.underline: manage.containsMouse
        MouseArea {
            id: manage
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: view.widget.backend.run("focus", "--focus")
        }
    }
}
