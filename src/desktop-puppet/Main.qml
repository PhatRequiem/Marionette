import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material

ApplicationWindow {
    id: win
    width: 540; height: 740
    visible: false
    color: previewMode ? "#17151e" : "transparent"
    title: qsTr("Marionette")
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
    Material.theme: Material.Dark
    Material.accent: theme.accent
    Material.roundedScale: theme.radius
    property bool paused: false
    property bool helpVisible: false
    readonly property bool textFocused: messageInput.activeFocus || replyText.activeFocus
    function placeInitial() {
        puppet.x = Math.max(0, win.width - puppet.width - 44)
        puppet.y = Math.max(0, win.height - puppet.height - 24)
        updateInput()
    }
    function updateInput() {
        var top = bubble.visible ? bubble.y : character.y
        backend.inputArea(puppet.x, puppet.y + top, puppet.width, puppet.height - top)
    }
    function giggle() { character.forceActiveFocus(); character.gesture() }
    function sendMessage() { chat.send(messageInput.text) }
    onWidthChanged: { puppet.x = Math.min(puppet.x, Math.max(0, width - puppet.width)); updateInput() }
    onHeightChanged: { puppet.y = Math.min(puppet.y, Math.max(0, height - puppet.height)); updateInput() }
    Shortcut { sequence: "Q"; enabled: !win.textFocused; context: Qt.ApplicationShortcut; onActivated: Qt.quit() }
    Shortcut { sequence: "Escape"; enabled: !win.textFocused; context: Qt.ApplicationShortcut; onActivated: Qt.quit() }
    Shortcut { sequence: "Space"; enabled: !win.textFocused; context: Qt.ApplicationShortcut; onActivated: win.paused = !win.paused }
    Shortcut { sequence: "?"; enabled: !win.textFocused; context: Qt.ApplicationShortcut; onActivated: win.helpVisible = !win.helpVisible }
    Connections {
        target: chat
        function onAnswered() { messageInput.clear(); replyScroll.contentItem.contentY = 0 }
        function onCleared() { messageInput.clear(); win.helpVisible = false }
        function onCloseRequested() { win.close() }
    }
    Item {
        id: puppet
        objectName: "puppet"
        width: Math.min(360, win.width); height: Math.min(680, win.height)
        readonly property real bubbleSpace: Math.max(80, height - 480)
        x: Math.max(0, win.width - width - 44)
        y: Math.max(0, win.height - height - 24)
        onXChanged: win.updateInput()
        onYChanged: win.updateInput()
        onHeightChanged: win.updateInput()
        LayoutMirroring.enabled: Qt.application.layoutDirection === Qt.RightToLeft
        LayoutMirroring.childrenInherit: true
        Rectangle {
            id: bubble
            objectName: "replyBubble"
            width: parent.width
            height: Math.min(parent.bubbleSpace, Math.max(80, replyText.contentHeight + 52))
            y: parent.bubbleSpace - height
            onYChanged: win.updateInput()
            visible: win.helpVisible || chat.reply.length > 0 || chat.error.length > 0
            onVisibleChanged: win.updateInput()
            color: "#ed201b2b"; radius: theme.radius
            border.color: theme.accent
            Rectangle {
                width: 12; height: 12; rotation: 45; z: -1
                anchors.horizontalCenter: parent.horizontalCenter
                y: parent.height - 6
                color: parent.color; border.color: theme.accent
            }
            ScrollView {
                id: replyScroll
                anchors.fill: parent; anchors.margins: 12; anchors.topMargin: 36
                clip: true
                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                TextArea {
                    id: replyText
                    objectName: "replyText"
                    readOnly: true; selectByMouse: true
                    wrapMode: TextEdit.Wrap; textFormat: TextEdit.PlainText
                    color: "#f5efff"; font.pixelSize: 14
                    padding: 0; background: null
                    text: win.helpVisible ? qsTr("Enter: send • Shift+Enter: new line\nClick her to giggle • Drag her to move\nOutside text: Space pauses, Q / Esc closes\nClose detaches the puppet; main chat keeps running.") : (chat.error || chat.reply)
                    Keys.onEscapePressed: character.forceActiveFocus()
                }
            }
            ToolButton {
                objectName: "dismissReply"
                anchors.top: parent.top; anchors.right: parent.right; anchors.margins: 3
                width: 30; height: 30; padding: 0
                contentItem: Text {
                    text: "×"; color: "#f5efff"; font.pixelSize: 20
                    horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                }
                Accessible.name: qsTr("Dismiss bubble")
                onClicked: { win.helpVisible = false; chat.dismiss() }
            }
        }
        PuppetAnimation {
            id: character
            x: (parent.width - width) / 2
            y: parent.bubbleSpace + 8; width: 280; height: 320
            playing: !win.paused
        }
        MouseArea {
            id: moveArea
            objectName: "moveArea"
            x: character.x + 20; y: character.y; width: character.width - 40; height: character.height
            cursorShape: pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor
            drag.target: puppet
            drag.minimumX: 0; drag.maximumX: Math.max(0, win.width - puppet.width)
            drag.minimumY: 0; drag.maximumY: Math.max(0, win.height - puppet.height)
            property bool moved: false
            onPressed: moved = false
            onPositionChanged: if (drag.active) moved = true
            onClicked: if (!moved) win.giggle()
            Accessible.role: Accessible.Button
            Accessible.name: qsTr("Click Marionette to giggle; drag to move")
            Accessible.onPressAction: win.giggle()
        }
        Rectangle {
            id: composer
            x: 0; y: character.y + character.height + 8
            width: parent.width; height: 96
            radius: theme.radius; color: "#ed201b2b"; border.color: theme.accent
            ScrollView {
                anchors.left: parent.left; anchors.top: parent.top; anchors.bottom: parent.bottom
                anchors.margins: 10; width: parent.width - 88
                clip: true
                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                TextArea {
                    id: messageInput
                    objectName: "messageInput"
                    placeholderText: qsTr("Message Marionette…")
                    readOnly: chat.busy; selectByMouse: true
                    wrapMode: TextEdit.Wrap; textFormat: TextEdit.PlainText
                    color: "#f5efff"; font.pixelSize: 14
                    padding: 0; background: null
                    Keys.priority: Keys.BeforeItem
                    Keys.onPressed: event => {
                        if ((event.key === Qt.Key_Return || event.key === Qt.Key_Enter) && !(event.modifiers & Qt.ShiftModifier)) {
                            win.sendMessage(); event.accepted = true
                        } else if (event.key === Qt.Key_Escape) {
                            character.forceActiveFocus(); event.accepted = true
                        }
                    }
                }
            }
            Button {
                objectName: "sendButton"
                anchors.right: parent.right; anchors.bottom: parent.bottom; anchors.margins: 8
                width: 68; height: 36; font.pixelSize: 14
                leftPadding: 8; rightPadding: 8; text: qsTr("Send")
                enabled: !chat.busy && messageInput.text.trim().length > 0
                onClicked: win.sendMessage()
            }
        }
        Row {
            anchors.bottom: parent.bottom; anchors.horizontalCenter: parent.horizontalCenter
            spacing: 4
            Button { font.pixelSize: 12; leftPadding: 8; rightPadding: 8; width: 82; height: 36; text: win.paused ? qsTr("Resume") : qsTr("Pause"); onClicked: win.paused = !win.paused }
            Button { font.pixelSize: 12; leftPadding: 8; rightPadding: 8; width: 70; height: 36; text: qsTr("Help"); onClicked: win.helpVisible = !win.helpVisible }
            Button { font.pixelSize: 12; leftPadding: 8; rightPadding: 8; width: 70; height: 36; text: qsTr("Close"); onClicked: win.close() }
        }
    }
}
