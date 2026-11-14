// One plan, laid out like the Reading Plans card on Logos's home page:
// cover · [streak] [time] [overdue] / title / summary · progress ring
import QtQuick
import QtQuick.Layouts
import org.kde.plasma.components as PlasmaComponents
import org.kde.kirigami as Kirigami

ColumnLayout {
    id: row
    required property var plan
    signal openUrl(string url)

    property bool expanded: false
    readonly property bool overdue: plan.behind !== null && plan.behind > 0
    spacing: 0

    MouseArea {
        id: hit
        Layout.fillWidth: true
        Layout.preferredHeight: content.implicitHeight + Kirigami.Units.largeSpacing * 2
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: {
            if (row.plan.readings.length === 1)
                row.openUrl(row.plan.readings[0].url)
            else
                row.expanded = !row.expanded
        }

        Rectangle {
            anchors.fill: parent
            radius: Kirigami.Units.cornerRadius
            color: Kirigami.Theme.highlightColor
            opacity: hit.containsMouse ? 0.12 : 0
            Behavior on opacity { NumberAnimation { duration: Kirigami.Units.shortDuration } }
        }

        RowLayout {
            id: content
            anchors.fill: parent
            anchors.margins: Kirigami.Units.largeSpacing
            spacing: Kirigami.Units.largeSpacing

            // Cover
            Item {
                Layout.preferredWidth: Kirigami.Units.gridUnit * 2.2
                Layout.preferredHeight: Kirigami.Units.gridUnit * 3
                Layout.alignment: Qt.AlignTop
                Image {
                    id: cover
                    anchors.fill: parent
                    source: row.plan.cover ? "file://" + row.plan.cover : ""
                    fillMode: Image.PreserveAspectFit
                    horizontalAlignment: Image.AlignLeft
                    verticalAlignment: Image.AlignTop
                    asynchronous: true
                    smooth: true
                    mipmap: true
                }
                Rectangle {
                    anchors.fill: parent
                    visible: cover.status !== Image.Ready
                    radius: Kirigami.Units.cornerRadius
                    color: Kirigami.Theme.alternateBackgroundColor
                    Kirigami.Icon {
                        anchors.centerIn: parent
                        width: Kirigami.Units.iconSizes.medium
                        height: width
                        source: "view-calendar-day"
                    }
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignVCenter
                spacing: Kirigami.Units.smallSpacing / 2

                // Chips: streak · time · overdue
                RowLayout {
                    spacing: Kirigami.Units.largeSpacing
                    visible: row.plan.streak > 0 || row.plan.minutes || row.plan.dueLabel

                    PlasmaComponents.Label {
                        visible: row.plan.streak > 0
                        text: "🔥 " + row.plan.streak
                        font: Kirigami.Theme.smallFont
                        color: Kirigami.Theme.neutralTextColor
                        leftPadding: Kirigami.Units.smallSpacing; rightPadding: Kirigami.Units.smallSpacing
                        background: Rectangle {
                            radius: height / 2
                            color: Kirigami.Theme.neutralBackgroundColor
                        }
                    }
                    RowLayout {
                        visible: !!row.plan.minutes
                        spacing: 2
                        Kirigami.Icon {
                            source: "chronometer"
                            Layout.preferredWidth: Kirigami.Units.iconSizes.small
                            Layout.preferredHeight: Kirigami.Units.iconSizes.small
                            opacity: 0.7
                        }
                        PlasmaComponents.Label {
                            text: i18nc("reading time in minutes", "%1m", row.plan.minutes)
                            font: Kirigami.Theme.smallFont
                            opacity: 0.8
                        }
                    }
                    RowLayout {
                        visible: row.plan.dueLabel !== ""
                        spacing: 2
                        Kirigami.Icon {
                            source: "view-calendar"
                            Layout.preferredWidth: Kirigami.Units.iconSizes.small
                            Layout.preferredHeight: Kirigami.Units.iconSizes.small
                            color: Kirigami.Theme.negativeTextColor
                            isMask: true
                        }
                        PlasmaComponents.Label {
                            text: row.plan.dueLabel
                            font: Kirigami.Theme.smallFont
                            color: Kirigami.Theme.negativeTextColor
                        }
                    }
                }

                PlasmaComponents.Label {
                    Layout.fillWidth: true
                    text: row.plan.title
                    font.bold: true
                    elide: Text.ElideRight
                }
                PlasmaComponents.Label {
                    Layout.fillWidth: true
                    text: row.plan.summary
                    font: Kirigami.Theme.smallFont
                    opacity: 0.7
                    elide: Text.ElideRight
                }
            }

            ProgressRing {
                Layout.preferredWidth: Kirigami.Units.gridUnit * 1.4
                Layout.preferredHeight: Layout.preferredWidth
                Layout.alignment: Qt.AlignVCenter
                progress: row.plan.progress
                color: row.overdue ? Kirigami.Theme.negativeTextColor : Kirigami.Theme.positiveTextColor
            }
        }

        PlasmaComponents.ToolTip {
            text: row.plan.readings.map(r => r.label).join("\n")
                  + "\n" + i18n("Session %1 of %2", row.plan.session, row.plan.total)
        }
    }

    // Individual readings, when a session has more than one
    Repeater {
        model: row.expanded ? row.plan.readings : []
        PlasmaComponents.ItemDelegate {
            required property var modelData
            Layout.fillWidth: true
            Layout.leftMargin: Kirigami.Units.gridUnit * 3
            icon.name: "bookmarks"
            text: modelData.label
            onClicked: row.openUrl(modelData.url)
        }
    }
}
