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
            text: i18n("From your library")
            elide: Text.ElideRight
        }
        PlasmaComponents.BusyIndicator {
            visible: shelf.widget.loading
            running: visible
            Layout.preferredWidth: Kirigami.Units.iconSizes.small
            Layout.preferredHeight: Layout.preferredWidth
        }
        PlasmaComponents.ToolButton {
            icon.name: "media-playlist-shuffle"
            onClicked: shelf.widget.refresh(true)
            PlasmaComponents.ToolTip { text: i18n("Show different books") }
        }
    }

    readonly property var sermonBooks: widget.books.filter(b => !!b.sermon)
    readonly property var libraryBooks: widget.books.filter(b => !b.sermon)
    readonly property var sermon: sermonBooks.length ? sermonBooks[0].sermon : null

    function shelfRows(n, grid) {
        return Math.max(1, Math.ceil(n / Math.max(1, grid.columns)))
    }

    // Commentaries for your next (or latest) sermon, opening at its passage.
    Kirigami.Heading {
        visible: shelf.sermon !== null
        Layout.fillWidth: true
        Layout.leftMargin: Kirigami.Units.largeSpacing
        level: 5
        opacity: 0.8
        elide: Text.ElideRight
        text: shelf.sermon ? (shelf.sermon.date
              ? i18n("For your sermon on %1 · %2", shelf.sermon.passage,
                     Qt.formatDate(new Date(shelf.sermon.date + "T12:00:00"), "ddd d MMM"))
              : i18n("For your sermon on %1", shelf.sermon.passage)) : ""
    }
    ShelfGrid {
        id: sermonGrid
        visible: shelf.sermon !== null
        shelf: shelf
        model: shelf.sermonBooks
        interactive: false
        Layout.fillWidth: true
        Layout.preferredHeight: shelf.shelfRows(count, sermonGrid) * cellHeight
    }

    Kirigami.Heading {
        visible: shelf.sermon !== null
        Layout.fillWidth: true
        Layout.leftMargin: Kirigami.Units.largeSpacing
        level: 5
        opacity: 0.8
        text: i18n("Unread and well rated")
    }
    ShelfGrid {
        id: grid
        shelf: shelf
        model: shelf.libraryBooks.slice(0, Math.max(columns, fits))
        Layout.fillWidth: true
        Layout.fillHeight: true
    }

    PlasmaComponents.Label {
        Layout.fillWidth: true
        Layout.leftMargin: Kirigami.Units.largeSpacing
        visible: shelf.widget.books.length === 0 && !shelf.widget.loading
        text: shelf.widget.error || i18n("Nothing to show yet")
        wrapMode: Text.Wrap
        opacity: 0.7
    }
}
