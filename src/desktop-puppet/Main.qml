import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material

ApplicationWindow {
    id: win
    width: 520; height: 600
    visible: false
    color: previewMode ? "#17151e" : "transparent"
    title: qsTr("Marionette puppet preview")
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
    Material.theme: Material.Dark
    Material.accent: theme.accent
    Material.roundedScale: theme.radius
    property bool paused: false
    property bool greeting: false
    property bool helpVisible: false
    function placeInitial() { puppet.x = Math.max(0, win.width - puppet.width - 44); puppet.y = Math.max(0, win.height - puppet.height - 44); updateInput() }
    function updateInput() { backend.inputArea(puppet.x, puppet.y, puppet.width, puppet.height) }
    function greet() { greeting = true; greetingTimer.restart(); bounce.restart() }
    onWidthChanged: { puppet.x = Math.min(puppet.x, Math.max(0, width - puppet.width)); updateInput() }
    onHeightChanged: { puppet.y = Math.min(puppet.y, Math.max(0, height - puppet.height)); updateInput() }
    Shortcut { sequence: "Q"; context: Qt.ApplicationShortcut; onActivated: Qt.quit() }
    Shortcut { sequence: "Escape"; context: Qt.ApplicationShortcut; onActivated: Qt.quit() }
    Shortcut { sequence: "Space"; context: Qt.ApplicationShortcut; onActivated: win.paused = !win.paused }
    Shortcut { sequence: "?"; context: Qt.ApplicationShortcut; onActivated: win.helpVisible = !win.helpVisible }
    Timer { id: greetingTimer; interval: 2600; onTriggered: win.greeting = false }
    Item {
        id: puppet
        objectName: "puppet"
        width: 280; height: 430
        x: Math.max(0, win.width - width - 44)
        y: Math.max(0, win.height - height - 44)
        onXChanged: win.updateInput()
        onYChanged: win.updateInput()
        LayoutMirroring.enabled: Qt.application.layoutDirection === Qt.RightToLeft
        LayoutMirroring.childrenInherit: true
        Rectangle {
            id: bubble
            anchors.top: parent.top; anchors.horizontalCenter: parent.horizontalCenter
            width: 270; height: 62
            visible: win.greeting || win.helpVisible
            color: "#ed201b2b"; radius: theme.radius
            border.color: theme.accent
            Text {
                anchors.fill: parent; anchors.margins: 8
                color: "#f5efff"; font.pixelSize: 13
                wrapMode: Text.WordWrap; horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                text: win.helpVisible ? qsTr("Drag to move • Click to greet\nSpace: pause • Q / Esc: close") : qsTr("Hello! Here I am.")
            }
        }
        Item {
            id: figure
            y: 66; width: parent.width; height: 320
            property real lift: 0
            transform: [Rotation { origin.x: 140; origin.y: 290; angle: sway.angle }, Translate { y: figure.lift }]
            QtObject { id: sway; property real angle: -1.3 }
            SequentialAnimation {
                running: !win.paused; loops: Animation.Infinite
                NumberAnimation { target: sway; property: "angle"; from: -1.3; to: 1.3; duration: 1800; easing.type: Easing.InOutSine }
                NumberAnimation { target: sway; property: "angle"; from: 1.3; to: -1.3; duration: 1800; easing.type: Easing.InOutSine }
            }
            SequentialAnimation {
                id: bounce
                NumberAnimation { target: figure; property: "lift"; to: -12; duration: 160; easing.type: Easing.OutQuad }
                NumberAnimation { target: figure; property: "lift"; to: 0; duration: 320; easing.type: Easing.OutBounce }
            }
            Image { anchors.fill: parent; source: "qrc:/assets/puppet.png"; fillMode: Image.PreserveAspectFit; smooth: false; mipmap: false }
        }
        MouseArea {
            id: moveArea
            objectName: "moveArea"
            x: 20; y: 66; width: parent.width - 40; height: 320
            cursorShape: pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor
            drag.target: puppet
            drag.minimumX: 0; drag.maximumX: Math.max(0, win.width - puppet.width)
            drag.minimumY: 0; drag.maximumY: Math.max(0, win.height - puppet.height)
            property bool moved: false
            onPressed: moved = false
            onPositionChanged: if (drag.active) moved = true
            onClicked: if (!moved) win.greet()
            Accessible.role: Accessible.Button
            Accessible.name: qsTr("Greet Marionette; drag to move")
            Accessible.onPressAction: win.greet()
        }
        Row {
            anchors.bottom: parent.bottom; anchors.horizontalCenter: parent.horizontalCenter
            spacing: 4
            Button { font.pixelSize: 12; leftPadding: 8; rightPadding: 8; width: 82; height: 36; text: win.paused ? qsTr("Resume") : qsTr("Pause"); onClicked: win.paused = !win.paused }
            Button { font.pixelSize: 12; leftPadding: 8; rightPadding: 8; width: 70; height: 36; text: qsTr("Help"); onClicked: win.helpVisible = !win.helpVisible }
            Button { font.pixelSize: 12; leftPadding: 8; rightPadding: 8; width: 70; height: 36; text: qsTr("Close"); onClicked: Qt.quit() }
        }
    }
}
