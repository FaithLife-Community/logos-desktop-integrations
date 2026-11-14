import QtQuick
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import org.kde.kcmutils as KCM

KCM.SimpleKCM {
    property alias cfg_bookCount: count.value
    property alias cfg_tilt: tilt.checked

    Kirigami.FormLayout {
        QQC2.SpinBox {
            id: count
            Kirigami.FormData.label: i18n("Books on the shelf:")
            from: 3; to: 36
        }
        QQC2.CheckBox {
            id: tilt
            Kirigami.FormData.label: i18n("Effects:")
            text: i18n("Tilt covers towards the pointer")
        }
    }
}
