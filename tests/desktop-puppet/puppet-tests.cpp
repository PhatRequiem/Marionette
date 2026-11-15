#include <QtTest>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QQuickWindow>
#include <QQuickItem>
#include <QQuickStyle>
#include <QTemporaryDir>
#include <QFile>
#include <QJSEngine>
#include <QLocalServer>
#include <QJsonDocument>
#include <QJsonObject>
#include <QSaveFile>
#include <QProcess>
#include <QScopeGuard>
#include "backend.h"
#include "chatclient.h"
#include "theme.h"
#include "translator.h"

class PuppetTests : public QObject {
    Q_OBJECT
    static void descriptor(const QString &root, const QString &generation, const QString &session = "synthetic-session") {
        QDir().mkpath(root + "/session");
        QSaveFile file(root + "/session/log-session.json");
        QVERIFY(file.open(QIODevice::WriteOnly));
        file.write(QJsonDocument(QJsonObject{{"session",session},{"generation",generation}}).toJson());
        QVERIFY(file.commit());
    }
private slots:
    void pythonBackendIntegration() {
        QTemporaryDir temporary;
        QVERIFY(temporary.isValid());
        const auto repo = QDir(QCoreApplication::applicationDirPath()).absoluteFilePath("../../..");
        QProcess process;
        process.start(repo + "/runtime/agent/bin/python", {repo + "/tests/desktop-puppet/chat-fixture.py",temporary.path()});
        QVERIFY(process.waitForStarted(5000));
        // Always stop the disposable fixture and let its actual recorders drain.
        const auto cleanup = qScopeGuard([&] {
            process.terminate();
            if (!process.waitForFinished(10000)) { process.kill(); process.waitForFinished(); }
        });
        QTRY_VERIFY_WITH_TIMEOUT(process.canReadLine(),10000);
        QCOMPARE(process.readLine().trimmed(), "ready");
        ChatClient chat(temporary.path());
        QVERIFY(chat.send("Synthetic native client input"));
        QTRY_VERIFY_WITH_TIMEOUT(!chat.busy(),10000);
        QVERIFY2(chat.error().isEmpty(),qPrintable(chat.error()));
        QCOMPARE(chat.reply(), "Synthetic local reply.");
        QVERIFY(chat.send("/resetmemory"));
        QTRY_VERIFY_WITH_TIMEOUT(!chat.busy(),15000);
        QVERIFY2(chat.error().isEmpty(),qPrintable(chat.error()));
        QVERIFY(chat.reply().startsWith("Memory reset."));
        QVERIFY(chat.send("Synthetic input after reset"));
        QTRY_VERIFY_WITH_TIMEOUT(!chat.busy(),10000);
        QCOMPARE(chat.reply(), "Synthetic local reply.");
    }
    void chatInputRepliesAndReset() {
        QTemporaryDir temporary;
        QVERIFY(temporary.isValid());
        descriptor(temporary.path(), "epoch-one");
        QLocalServer server;
        QVERIFY(server.listen(temporary.filePath("session/chat.sock")));
        Theme theme(temporary.path());
        Translator translator(temporary.filePath("language"));
        Backend backend;
        ChatClient chat(temporary.path());
        QQmlApplicationEngine engine;
        QStringList warnings;
        connect(&engine, &QQmlEngine::warnings, this, [&](const QList<QQmlError> &errors) {
            for (const auto &error : errors) warnings << error.toString();
        });
        engine.rootContext()->setContextProperty("theme", &theme);
        engine.rootContext()->setContextProperty("translator", &translator);
        engine.rootContext()->setContextProperty("backend", &backend);
        engine.rootContext()->setContextProperty("chat", &chat);
        engine.rootContext()->setContextProperty("previewMode", true);
        engine.load(QUrl("qrc:/Main.qml"));
        QVERIFY(!engine.rootObjects().isEmpty());
        auto *window = qobject_cast<QQuickWindow *>(engine.rootObjects().first());
        backend.setWindow(window);
        window->show();
        QVERIFY(QMetaObject::invokeMethod(window, "placeInitial"));
        QVERIFY(QTest::qWaitForWindowExposed(window));
        auto *input = window->findChild<QQuickItem *>("messageInput");
        auto *reply = window->findChild<QQuickItem *>("replyText");
        auto *bubble = window->findChild<QQuickItem *>("replyBubble");
        auto *character = window->findChild<QQuickItem *>("characterAnimation");
        QVERIFY(input && reply && bubble && character);
        input->forceActiveFocus();
        QTest::keyClick(window, Qt::Key_Q);
        QTest::keyClick(window, Qt::Key_Space);
        QTest::keyClick(window, Qt::Key_Question);
        QVERIFY(window->isVisible());
        QVERIFY(!window->property("paused").toBool());
        QVERIFY(!window->property("helpVisible").toBool());
        QVERIFY(input->property("text").toString().contains(' '));
        QTest::keyClick(window, Qt::Key_Return, Qt::ShiftModifier);
        QVERIFY(input->property("text").toString().contains('\n'));
        input->setProperty("text", "Hello from the desktop");
        QTest::keyClick(window, Qt::Key_Return);
        QTRY_VERIFY(server.hasPendingConnections());
        QScopedPointer<QLocalSocket> peer(server.nextPendingConnection());
        QTRY_VERIFY(peer->canReadLine());
        auto request = QJsonDocument::fromJson(peer->readLine()).object();
        QCOMPARE(request.value("source").toString(), "desktop");
        QCOMPARE(request.value("message").toString(), "Hello from the desktop");
        QCOMPARE(request.value("session").toString(), "synthetic-session");
        QVERIFY(!request.contains("sender_id"));
        QVERIFY(chat.busy());
        QVERIFY(!bubble->isVisible()); // No waiting bubble or scripted greeting.
        const auto hover = character->property("hoverOffset").toReal();
        QTest::qWait(250);
        QCOMPARE(character->property("animationKind").toString(), "idle");
        QVERIFY(character->property("hoverOffset").toReal() != hover);
        QVERIFY(!chat.send("duplicate"));
        const QString answer = "I'm here. Your messages reach the same local chat engine, and my replies appear here.";
        const auto response = QJsonDocument(QJsonObject{{"answer",answer},{"finish","stop"},
            {"session","synthetic-session"},{"generation","epoch-one"}}).toJson(QJsonDocument::Compact) + '\n';
        peer->write(response.left(20)); peer->flush();
        QTest::qWait(30);
        QVERIFY(chat.busy());
        peer->write(response.mid(20)); peer->flush();
        QTRY_COMPARE(chat.reply(), answer);
        QVERIFY(!chat.busy());
        QCOMPARE(input->property("text").toString(), "");
        QCOMPARE(reply->property("text").toString(), answer);
        QCOMPARE(reply->property("textFormat").toInt(), 0); // PlainText.
        QCOMPARE(character->property("animationKind").toString(), "idle");
        QVERIFY(bubble->isVisible());
        const QString captures = qEnvironmentVariable("PUPPET_TEST_CAPTURES");
        if (!captures.isEmpty()) {
            QDir().mkpath(captures);
            QTest::qWait(100);
            QVERIFY(window->grabWindow().save(captures + "/chat.png"));
        }
        QVERIFY(chat.send("Long reply test"));
        QTRY_VERIFY(server.hasPendingConnections());
        peer.reset(server.nextPendingConnection());
        QTRY_VERIFY(peer->canReadLine()); peer->readLine();
        const QString longAnswer = QString("A long plain-text reply with <b>literal markup</b>.\n").repeated(100);
        peer->write(QJsonDocument(QJsonObject{{"answer",longAnswer},{"finish","stop"},
            {"session","synthetic-session"},{"generation","epoch-one"}}).toJson(QJsonDocument::Compact) + '\n');
        peer->flush();
        QTRY_COMPARE(chat.reply(),longAnswer);
        QVERIFY(reply->property("contentHeight").toReal() > bubble->height());
        QVERIFY(bubble->height() <= 200);
        auto *dismiss = window->findChild<QQuickItem *>("dismissReply");
        QVERIFY(dismiss);
        QTest::mouseClick(window,Qt::LeftButton,{},dismiss->mapToScene(QPointF(15,15)).toPoint());
        QTRY_VERIFY(chat.reply().isEmpty());
        input->setProperty("text", "OLD_SECRET pending input");
        QVERIFY(chat.send(input->property("text").toString()));
        QTRY_VERIFY(server.hasPendingConnections());
        peer.reset(server.nextPendingConnection());
        QTRY_VERIFY(peer->canReadLine()); peer->readLine();
        descriptor(temporary.path(), "epoch-two");
        QTRY_VERIFY(chat.reply().isEmpty());
        QTRY_COMPARE(input->property("text").toString(), "");
        peer->write(response); peer->flush();
        QTRY_VERIFY(!chat.busy());
        QVERIFY(chat.reply().isEmpty());
        QVERIFY(!bubble->isVisible());
        QVERIFY(!server.hasPendingConnections()); // No automatic replay after reset.
        // A reset requested here may acknowledge its new generation.
        QVERIFY(chat.send("/resetmemory"));
        QTRY_VERIFY(server.hasPendingConnections());
        peer.reset(server.nextPendingConnection());
        QTRY_VERIFY(peer->canReadLine()); peer->readLine();
        descriptor(temporary.path(), "epoch-three");
        peer->write(QJsonDocument(QJsonObject{{"answer","Memory reset."},{"finish","resetmemory"},
            {"session","synthetic-session"},{"generation","epoch-three"}}).toJson(QJsonDocument::Compact) + '\n');
        peer->flush();
        QTRY_COMPARE(chat.reply(), "Memory reset.");
        descriptor(temporary.path(), "epoch-three", "restarted-session");
        QTRY_VERIFY(chat.reply().isEmpty());
        QFile blocked(temporary.filePath("memory-reset-incomplete.json"));
        QVERIFY(blocked.open(QIODevice::WriteOnly)); blocked.write("{}"); blocked.close();
        QVERIFY(!chat.send("must not run"));
        QVERIFY(!chat.error().isEmpty());
        QVERIFY(!server.hasPendingConnections());
        QVERIFY2(warnings.isEmpty(), qPrintable(warnings.join('\n')));
        window->close();
    }
    void offlineAndMalformedReply() {
        QTemporaryDir temporary;
        ChatClient chat(temporary.path());
        QVERIFY(!chat.send("offline"));
        QVERIFY(!chat.error().isEmpty());
        descriptor(temporary.path(), "epoch");
        QLocalServer server;
        QVERIFY(server.listen(temporary.filePath("session/chat.sock")));
        QVERIFY(chat.send("message"));
        QTRY_VERIFY(server.hasPendingConnections());
        QScopedPointer<QLocalSocket> peer(server.nextPendingConnection());
        QTRY_VERIFY(peer->canReadLine()); peer->readLine();
        peer->write("not json\n"); peer->flush();
        QTRY_VERIFY(!chat.busy());
        QVERIFY(!chat.error().isEmpty());
        QVERIFY(chat.reply().isEmpty());
        QVERIFY(!server.hasPendingConnections());
    }
    void idleArmDeformation() {
        QJSEngine js;
        QFile source(":/PuppetMotion.js");
        QVERIFY(source.open(QIODevice::ReadOnly));
        QVERIFY(!js.evaluate(QString::fromUtf8(source.readAll())).isError());
        auto result = js.evaluate(R"JS(
            var low = Infinity, high = -Infinity;
            for (var t = 0; t < 12; t += .1) {
                for (var point of [[270,180],[270,230],[220,270],[325,270],[250,400]]) {
                    if (idleArmOffset(point[0], point[1], t) !== 0)
                        throw new Error('Arm motion displaced the neck, body or legs');
                }
                var wrist = idleArmOffset(162, 212, t);
                low = Math.min(low, wrist); high = Math.max(high, wrist);
                for (var x = 98; x < 440; x += 4) {
                    for (var y = 168; y < 288; y += 8) {
                        var top = Math.round(y + idleArmOffset(x, y, t));
                        var bottom = Math.round(y+8 + idleArmOffset(x, y+8, t));
                        if (bottom <= top) throw new Error('Arm surface folded over');
                    }
                }
            }
            if (high-low < 16) throw new Error('Wrist movement is too small to see');
            true;
        )JS");
        QVERIFY2(!result.isError(), qPrintable(result.toString()));
        QVERIFY(result.toBool());
    }
    void animationState() {
        QJSEngine js;
        QFile source(":/PuppetMotion.js");
        QVERIFY(source.open(QIODevice::ReadOnly));
        QVERIFY(!js.evaluate(QString::fromUtf8(source.readAll())).isError());
        // Simulate varied idle holds, then request a giggle during an up-pose
        // blink. It must finish that clip, lower the legs, and return to idle.
        auto result = js.evaluate(R"JS(
            var seed = 19;
            var p = new Player(function() {
                seed = (seed * 1664525 + 1013904223) >>> 0;
                return seed / 4294967296;
            });
            var sawBlink = false, sawUp = false, sawDown = false;
            for (var i = 0; i < 12000; ++i) {
                p.tick(.016);
                sawUp = sawUp || p.pose === 'up';
                sawDown = sawDown || p.pose === 'down';
                if (p.clipKind === 'blink') {
                    if (p.pose !== 'up') throw new Error('Blink with legs down');
                    sawBlink = true;
                }
            }
            if (!sawBlink || !sawUp || !sawDown) throw new Error('Idle states missing');
            for (var i = 0; i < 10000 && p.clipKind !== 'blink'; ++i) p.tick(.016);
            if (p.clipKind !== 'blink') throw new Error('No blink reached');
            p.giggle();
            var sawLowering = false, sawGiggle = false, finished = false;
            for (var i = 0; i < 500; ++i) {
                p.tick(.016);
                sawLowering = sawLowering || p.clipKind === 'to-down';
                if (p.mode === 'giggle') {
                    if (p.pose !== 'down' || p.clipKind) throw new Error('Giggle interrupted an idle clip');
                    sawGiggle = true;
                    p.giggle(); // Repeated clicks must not restart or queue loops.
                } else if (sawGiggle) {
                    finished = p.frame === 36 && p.pose === 'down' && !p.pendingGiggle;
                    break;
                }
            }
            if (!sawLowering || !sawGiggle || !finished) throw new Error('Giggle did not reset');
            true;
        )JS");
        QVERIFY2(!result.isError(), qPrintable(result.toString()));
        QVERIFY(result.toBool());
    }
    void interactionAndTranslation() {
        QTemporaryDir temporary;
        QVERIFY(temporary.isValid());
        Theme theme(temporary.path());
        const auto languagePath = temporary.filePath("language");
        Translator translator(languagePath);
        qApp->installTranslator(&translator);
        Backend backend;
        ChatClient chat(temporary.path());
        QQmlApplicationEngine engine;
        QObject::connect(&translator, &Translator::changed, &engine, &QQmlEngine::retranslate);
        QStringList warnings;
        QObject::connect(&engine, &QQmlEngine::warnings, this, [&](const QList<QQmlError> &errors) {
            for (const auto &error : errors) warnings << error.toString();
        });
        engine.rootContext()->setContextProperty("theme", &theme);
        engine.rootContext()->setContextProperty("translator", &translator);
        engine.rootContext()->setContextProperty("backend", &backend);
        engine.rootContext()->setContextProperty("chat", &chat);
        engine.rootContext()->setContextProperty("previewMode", true);
        engine.load(QUrl("qrc:/Main.qml"));
        QVERIFY(!engine.rootObjects().isEmpty());
        auto *window = qobject_cast<QQuickWindow *>(engine.rootObjects().first());
        QVERIFY(window);
        backend.setWindow(window);
        window->show();
        QVERIFY(QMetaObject::invokeMethod(window, "placeInitial"));
        QVERIFY(QTest::qWaitForWindowExposed(window));
        auto *puppet = window->findChild<QQuickItem *>("puppet");
        QVERIFY(puppet);
        QVERIFY(!window->mask().contains(QPoint(5, 5)));
        auto *character = window->findChild<QQuickItem *>("characterAnimation");
        QVERIFY(character);
        const QPoint inside(puppet->x() + puppet->width()/2, puppet->y() + character->y() + 160);
        QVERIFY(window->mask().contains(inside));
        QTest::mouseClick(window, Qt::LeftButton, {}, inside);
        QTRY_COMPARE(character->property("animationKind").toString(), QString("giggle"));
        QTest::keyClick(window, Qt::Key_Space);
        QTRY_VERIFY(window->property("paused").toBool());
        QTest::keyClick(window, Qt::Key_Space);
        QTRY_VERIFY(!window->property("paused").toBool());
        QTRY_VERIFY(character->property("ready").toBool());
        window->setProperty("paused", true);
        const int stoppedFrame = character->property("frameIndex").toInt();
        const auto stoppedHover = character->property("hoverOffset").toReal();
        const auto stoppedIdleMotion = character->property("idleMotionAmount").toReal();
        QTest::qWait(450);
        QCOMPARE(character->property("frameIndex").toInt(), stoppedFrame);
        QCOMPARE(character->property("hoverOffset").toReal(), stoppedHover);
        QCOMPARE(character->property("idleMotionAmount").toReal(), stoppedIdleMotion);
        window->setProperty("paused", false);
        QVERIFY(QMetaObject::invokeMethod(character, "gesture"));
        QTRY_COMPARE(character->property("animationKind").toString(), QString("giggle"));
        QTRY_COMPARE(character->property("frameIndex").toInt(), 2);
        window->setProperty("paused", true);
        QTest::qWait(50);
        const auto pausedGiggle = window->grabWindow();
        QTest::qWait(100);
        QCOMPARE(window->grabWindow(), pausedGiggle);
        const QString captures = qEnvironmentVariable("PUPPET_TEST_CAPTURES");
        if (!captures.isEmpty()) {
            QDir().mkpath(captures);
            QVERIFY(pausedGiggle.save(captures + "/giggle-bounce.png"));
        }
        window->setProperty("paused", false);
        QTRY_COMPARE(character->property("frameIndex").toInt(), 3);
        QVERIFY(character->property("hoverOffset").toReal() != stoppedHover);
        QTRY_COMPARE(character->property("frameIndex").toInt(), 0);
        QTRY_COMPARE(character->property("animationKind").toString(), QString("idle"));
        QCOMPARE(character->property("frameIndex").toInt(), 36);
        window->setProperty("paused", true);
        QImage previous;
        for (int frame : {24,31,32,33,34,35,36,37,38,39,40,41,42}) {
            character->setProperty("frameIndex", frame);
            QTest::qWait(50);
            const auto rendered = window->grabWindow();
            QVERIFY(!rendered.isNull());
            if (!previous.isNull()) QVERIFY(rendered != previous);
            previous = rendered;
            if (!captures.isEmpty()) {
                QDir().mkpath(captures);
                QVERIFY(rendered.save(captures + QString("/idle-%1.png").arg(frame)));
            }
        }
        if (!captures.isEmpty()) {
            auto player = character->property("player").value<QJSValue>();
            const auto savedTime = player.property("time");
            // Sample both ends of the arm wave in each idle pose for visual QA.
            for (int frame : {24,36}) {
                player.setProperty("frame", frame);
                for (int phase = 0; phase < 2; ++phase) {
                    player.setProperty("time", .8 + phase*1.8);
                    QVERIFY(QMetaObject::invokeMethod(character, "advance", Q_ARG(QVariant, 0.0)));
                    QTest::qWait(50);
                    QVERIFY(window->grabWindow().save(captures + QString("/arms-%1-%2.png").arg(frame).arg(phase)));
                }
            }
            player.setProperty("time", savedTime);
        }
        character->setProperty("animationKind", "giggle");
        previous = QImage();
        for (int frame = 0; frame < 7; ++frame) {
            character->setProperty("frameIndex", frame);
            QTest::qWait(50);
            const auto rendered = window->grabWindow();
            QVERIFY(!rendered.isNull());
            if (!previous.isNull()) QVERIFY(rendered != previous);
            previous = rendered;
            if (!captures.isEmpty()) QVERIFY(rendered.save(captures + QString("/giggle-%1.png").arg(frame)));
        }
        window->setProperty("paused", false);
        const auto oldX = puppet->x();
        QTest::mousePress(window, Qt::LeftButton, {}, inside);
        QTest::mouseMove(window, inside - QPoint(35, 0), 40);
        QTest::mouseMove(window, inside - QPoint(65, 0), 40);
        QTest::mouseRelease(window, Qt::LeftButton, {}, inside - QPoint(65, 0));
        QVERIFY(puppet->x() < oldX);
        QVERIFY(window->mask().contains(QPoint(puppet->x() + puppet->width()/2, puppet->y() + character->y() + 160)));
        QFile language(languagePath);
        QVERIFY(language.open(QIODevice::WriteOnly));
        language.write("da\n"); language.close();
        QTRY_COMPARE(translator.language(), QString("da"));
        QTRY_COMPARE(window->findChild<QQuickItem *>("messageInput")->property("placeholderText").toString(), QString::fromUtf8("Skriv til Marionette…"));
        window->setProperty("helpVisible",true);
        QTest::qWait(100);
        QVERIFY(!window->grabWindow().isNull());
        window->grabWindow().save(temporary.filePath("danish.png"));
        if (!captures.isEmpty()) QVERIFY(window->grabWindow().save(captures + "/danish-chat.png"));
        QVERIFY2(warnings.isEmpty(), qPrintable(warnings.join('\n')));
        window->close();
        QVERIFY(!window->isVisible());
        qApp->removeTranslator(&translator);
    }
};
int main(int argc, char **argv) {
    QGuiApplication app(argc, argv);
    QQuickStyle::setStyle("Material");
    PuppetTests tests;
    return QTest::qExec(&tests, argc, argv);
}
#include "puppet-tests.moc"
