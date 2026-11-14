// Covers standing on shelves, like a library's display stand.
import QtQuick
import QtQuick.Layouts
import org.kde.plasma.components as PlasmaComponents
import org.kde.kirigami as Kirigami

ColumnLayout {
    id: shelf
    required property var widget
    spacing: Kirigami.Units.smallSpacing

    readonly property real bookHeight: Kirigami.Units.gridUnit * 6.5
    readonly property real bookWidth: bookHeight * 0.68
    readonly property real plank: Kirigami.Units.smallSpacing * 2

    RowLayout {
        Layout.fillWidth: true
        Layout.leftMargin: Kirigami.Units.largeSpacing
        Layout.rightMargin: Kirigami.Units.smallSpacing
        Kirigami.Heading {
            Layout.fillWidth: true
            level: 3
            text: shelf.widget.sermonShelf ? i18n("For your sermon") : i18n("From your library")
            elide: Text.ElideRight
        }
        PlasmaComponents.BusyIndicator {
            visible: shelf.widget.loading
            running: visible
            Layout.preferredWidth: Kirigami.Units.iconSizes.small
            Layout.preferredHeight: Layout.preferredWidth
        }
        PlasmaComponents.ToolButton {
            visible: !shelf.widget.sermonShelf
            icon.name: "media-playlist-shuffle"
            onClicked: shelf.widget.refresh(true)
            PlasmaComponents.ToolTip { text: i18n("Show different books") }
        }
    }

    readonly property var sermon: widget.sermonShelf && widget.books.length ? widget.books[0].sermon : null

    // Sermon shelf: which passage and when
    PlasmaComponents.Label {
        visible: shelf.sermon !== null
        Layout.fillWidth: true
        Layout.leftMargin: Kirigami.Units.largeSpacing
        opacity: 0.8
        elide: Text.ElideRight
        text: shelf.sermon ? (shelf.sermon.date
              ? i18n("%1 · %2", shelf.sermon.passage,
                     Qt.formatDate(new Date(shelf.sermon.date + "T12:00:00"), "ddd d MMM"))
              : shelf.sermon.passage) : ""
    }
    ShelfGrid {
        id: grid
        shelf: shelf
        adaptive: true
        // the library shelf shows whole rows; the sermon shelf shows every commentary,
        // scrolling if they don't all fit
        model: shelf.widget.sermonShelf ? shelf.widget.books
                                        : shelf.widget.books.slice(0, Math.max(columns, fits))
        Layout.fillWidth: true
        Layout.fillHeight: true
    }

    PlasmaComponents.Label {
        Layout.fillWidth: true
        Layout.leftMargin: Kirigami.Units.largeSpacing
        visible: shelf.widget.books.length === 0 && !shelf.widget.loading
        text: shelf.widget.error || (shelf.widget.sermonShelf
              ? i18n("No sermon document with a passage found, or no commentaries you've rated for it")
              : i18n("Nothing to show yet"))
        wrapMode: Text.Wrap
        opacity: 0.7
    }
}
