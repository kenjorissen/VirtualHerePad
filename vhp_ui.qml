import QtQuick
import QtQuick.Window

Window {
    id: window
    required property var vhp
    width: 1280
    height: 800
    visible: true
    visibility: Window.FullScreen
    color: "#000000"
    title: "VirtualHerePad"

    property bool keyboardOpen: false
    // Mirrors vhp.columns. Declared here so both the hit-testing maths and the
    // key widths use one name; an undefined divisor silently made every key zero
    // wide, which drew a correctly-counted, completely invisible keyboard.
    readonly property int columns: vhp.columns

    // Exact touch maths: map a point to the key that owns its grid cell. This
    // mirrors vhp_keyboard.layout_grid, where every row spans `columns` cells.
    function codeAt(x, y, w, h) {
        var rows = vhp.rows;
        var rowHeight = h / rows.length;
        var row = Math.floor(y / rowHeight);
        if (row < 0 || row >= rows.length) {
            return -1;
        }
        var cell = Math.floor(x * window.columns / w);
        var keys = rows[row];
        var acc = 0;
        for (var i = 0; i < keys.length; i++) {
            acc += keys[i].span;
            if (cell < acc) {
                return keys[i].code;
            }
        }
        return -1;
    }

    component FlatButton: Rectangle {
        id: button
        property string text: ""
        property bool highlighted: false
        signal tapped

        radius: height * 0.22
        color: highlighted ? "#1c6b3a" : (buttonMouse.pressed ? "#2b3a4a" : "#16202b")
        border.color: highlighted ? "#43d17a" : "#3a4c60"
        border.width: 2

        Text {
            anchors.centerIn: parent
            text: button.text
            color: "#e8f1f8"
            font.bold: true
            font.pixelSize: Math.max(13, button.height * 0.32)
        }
        MouseArea {
            id: buttonMouse
            anchors.fill: parent
            onClicked: button.tapped()
        }
    }

    component HoldButton: Rectangle {
        id: hold
        property string text: ""
        property int holdMilliseconds: 2000
        property real progress: 0
        signal held

        function cancelHold() {
            fill.stop();
            hold.progress = 0;
            holdTimer.stop();
        }

        Connections {
            target: window
            function onActiveChanged() {
                if (!window.active) hold.cancelHold();
            }
        }

        radius: height * 0.22
        color: "#1b1214"
        border.color: holdArea.pressed ? "#e06c6c" : "#7a3030"
        border.width: 2
        clip: true

        NumberAnimation {
            id: fill
            target: hold
            property: "progress"
            from: 0
            to: 1
            duration: hold.holdMilliseconds
        }

        Rectangle {
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            width: hold.width * hold.progress
            color: "#a13333"
        }

        Text {
            anchors.centerIn: parent
            text: holdArea.pressed ? "KEEP HOLDING" : hold.text
            color: "#f6e7e7"
            font.bold: true
            font.pixelSize: Math.max(12, hold.height * 0.28)
        }

        MouseArea {
            id: holdArea
            anchors.fill: parent
            onPressed: {
                hold.progress = 0;
                fill.restart();
                holdTimer.restart();
            }
            onReleased: hold.cancelHold()
            onCanceled: hold.cancelHold()
            onExited: hold.cancelHold()
        }

        Timer {
            id: holdTimer
            interval: hold.holdMilliseconds
            onTriggered: {
                if (holdArea.pressed && holdArea.containsMouse) hold.held();
            }
        }
    }

    Item {
        id: topBar
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        height: Math.max(64, window.height * 0.12)

        FlatButton {
            id: toggleButton
            objectName: "keyboardToggle"
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.verticalCenter: parent.verticalCenter
            width: Math.min(parent.width * 0.36, 420)
            height: parent.height * 0.68
            highlighted: window.keyboardOpen
            text: window.keyboardOpen ? "HIDE KEYBOARD" : "KEYBOARD"
            onTapped: window.keyboardOpen = !window.keyboardOpen
        }

        Text {
            id: statusText
            anchors.left: parent.left
            anchors.leftMargin: 16
            anchors.verticalCenter: parent.verticalCenter
            width: Math.max(0, toggleButton.x - 32)
            elide: Text.ElideRight
            color: vhp.shared ? "#43d17a" : (vhp.connected ? "#c9a227" : "#c05a5a")
            font.pixelSize: Math.max(13, topBar.height * 0.22)
            font.bold: true
            text: vhp.connected ? (vhp.shared ? "PC KEYBOARD ACTIVE" : "WAITING FOR PC") : "BACKEND OFFLINE"
        }

        HoldButton {
            id: quitButton
            objectName: "holdQuit"
            anchors.right: parent.right
            anchors.rightMargin: 16
            anchors.verticalCenter: parent.verticalCenter
            width: Math.min(parent.width * 0.22, 220)
            height: parent.height * 0.68
            text: "HOLD 2s TO QUIT"
            onHeld: {
                vhp.stop();
                Qt.quit();
            }
        }
    }

    Column {
        id: keypad
        objectName: "keypad"
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: topBar.bottom
        anchors.bottom: bottomBar.top
        anchors.margins: 12
        visible: window.keyboardOpen

        Repeater {
            model: vhp.rows

            delegate: Row {
                id: keyRow
                // Declared explicitly: an unqualified modelData is not reachable as
                // `keyRow.modelData`, and an empty model silently draws nothing.
                required property var modelData
                height: keypad.height / vhp.rows.length
                spacing: 0

                Repeater {
                    model: keyRow.modelData

                    delegate: Item {
                        required property var modelData
                        width: keypad.width * modelData.span / Math.max(1, window.columns)
                        height: keyRow.height

                        Rectangle {
                            objectName: "keycap"
                            anchors.fill: parent
                            anchors.margins: 3
                            radius: 10
                            color: modelData.active ? "#2f6ea8" : "#1b2632"
                            border.color: modelData.active ? "#6fb6f0" : "#2d3d4d"
                            border.width: 1

                            Text {
                                objectName: "keycapLabel"
                                anchors.centerIn: parent
                                text: modelData.label
                                color: "#eaf2f8"
                                font.pixelSize: Math.max(11, parent.height * 0.34)
                            }
                        }
                    }
                }
            }
        }
    }

    MultiPointTouchArea {
        id: keypadTouch
        anchors.fill: keypad
        enabled: window.keyboardOpen
        minimumTouchPoints: 1
        maximumTouchPoints: 10

        property var mapping: ({})

        function sync(points) {
            var next = ({});
            for (var i = 0; i < points.length; i++) {
                var point = points[i];
                if (!point.pressed) {
                    continue;
                }
                var code = window.codeAt(point.x, point.y, keypadTouch.width, keypadTouch.height);
                if (code !== -1) {
                    next[point.id] = code;
                }
            }
            for (var id in mapping) {
                if (!(id in next) || next[id] !== mapping[id]) {
                    vhp.release(mapping[id]);
                }
            }
            for (var id2 in next) {
                if (mapping[id2] !== next[id2]) {
                    vhp.press(next[id2]);
                }
            }
            mapping = next;
        }

        onPressed: sync(touchPoints)
        onUpdated: sync(touchPoints)
        onReleased: sync(touchPoints)
        onCanceled: {
            for (var id in mapping) {
                vhp.release(mapping[id]);
            }
            mapping = ({});
        }
        Component.onDestruction: {
            for (var id in mapping) {
                vhp.release(mapping[id]);
            }
        }
    }

    Item {
        id: bottomBar
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: Math.max(62, window.height * 0.11)

        Text {
            anchors.left: parent.left
            anchors.leftMargin: 16
            anchors.verticalCenter: parent.verticalCenter
            color: vhp.connected ? "#8fb4d0" : "#c05a5a"
            font.pixelSize: Math.max(13, bottomBar.height * 0.22)
            text: "Brightness " + vhp.percent + "%"
        }

        Row {
            anchors.right: parent.right
            anchors.rightMargin: 16
            anchors.verticalCenter: parent.verticalCenter
            spacing: 10

            Repeater {
                model: vhp.layoutNames

                delegate: FlatButton {
                    height: bottomBar.height * 0.66
                    width: bottomBar.width * 0.13
                    highlighted: modelData.id === vhp.layout
                    text: modelData.label
                    onTapped: vhp.setLayout(modelData.id)
                }
            }

            FlatButton {
                height: bottomBar.height * 0.66
                width: bottomBar.width * 0.17
                text: "RELEASE KEYS"
                onTapped: vhp.clear()
            }

        }
    }
}
