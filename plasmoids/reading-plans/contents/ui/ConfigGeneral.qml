import QtQuick
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import org.kde.kcmutils as KCM

KCM.SimpleKCM {
    property alias cfg_maxPlans: maxPlans.value

    Kirigami.FormLayout {
        QQC2.SpinBox {
            id: maxPlans
            Kirigami.FormData.label: i18n("Plans shown per tab:")
            from: 1; to: 50
        }
    }
}
