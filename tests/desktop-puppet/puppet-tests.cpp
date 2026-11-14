#include <QtTest>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QQuickWindow>
#include <QQuickItem>
#include <QQuickStyle>
#include <QTemporaryDir>
#include <QFile>
#include "backend.h"
#include "theme.h"
#include "translator.h"

class PuppetTests : public QObject {
    Q_OBJECT
private slots:
    void interactionAndTranslation() {
        QTemporaryDir temporary;
        QVERIFY(temporary.isValid());
        Theme theme(temporary.path());
        const auto languagePath = temporary.filePath("language");
        Translator translator(languagePath);
        qApp->installTranslator(&translator);
        Backend backend;
        QQmlApplicationEngine engine;
        QObject::connect(&translator, &Translator::changed, &engine, &QQmlEngine::retranslate);
        QStringList warnings;
        QObject::connect(&engine, &QQmlEngine::warnings, this, [&](const QList<QQmlError> &errors) {
            for (const auto &error : errors) warnings << error.toString();
        });
        engine.rootContext()->setContextProperty("theme", &theme);
        engine.rootContext()->setContextProperty("translator", &translator);
        engine.rootContext()->setContextProperty("backend", &backend);
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
        const QPoint inside(puppet->x() + 140, puppet->y() + 210);
        QVERIFY(window->mask().contains(inside));
        QTest::mouseClick(window, Qt::LeftButton, {}, inside);
        QTRY_VERIFY(window->property("greeting").toBool());
        QTest::keyClick(window, Qt::Key_Space);
        QTRY_VERIFY(window->property("paused").toBool());
        QTest::keyClick(window, Qt::Key_Space);
        QTRY_VERIFY(!window->property("paused").toBool());
        auto *character = window->findChild<QQuickItem *>("characterAnimation");
        QVERIFY(character);
        window->setProperty("paused", true);
        const int stoppedFrame = character->property("frameIndex").toInt();
        QTest::qWait(450);
        QCOMPARE(character->property("frameIndex").toInt(), stoppedFrame);
        window->setProperty("paused", false);
        QVERIFY(QMetaObject::invokeMethod(character, "gesture"));
        QTRY_COMPARE(character->property("frameIndex").toInt(), 3);
        QTRY_COMPARE(character->property("frameIndex").toInt(), 0);
        window->setProperty("paused", true);
        QImage previous;
        const QString captures = qEnvironmentVariable("PUPPET_TEST_CAPTURES");
        for (int frame = 0; frame < 6; ++frame) {
            character->setProperty("frameIndex", frame);
            QTest::qWait(50);
            const auto rendered = window->grabWindow();
            QVERIFY(!rendered.isNull());
            if (!previous.isNull()) QVERIFY(rendered != previous);
            previous = rendered;
            if (!captures.isEmpty()) {
                QDir().mkpath(captures);
                QVERIFY(rendered.save(captures + QString("/frame-%1.png").arg(frame)));
            }
        }
        window->setProperty("paused", false);
        const auto oldX = puppet->x();
        QTest::mousePress(window, Qt::LeftButton, {}, inside);
        QTest::mouseMove(window, inside - QPoint(35, 0), 40);
        QTest::mouseMove(window, inside - QPoint(65, 0), 40);
        QTest::mouseRelease(window, Qt::LeftButton, {}, inside - QPoint(65, 0));
        QVERIFY(puppet->x() < oldX);
        QVERIFY(window->mask().contains(QPoint(puppet->x() + 140, puppet->y() + 210)));
        QFile language(languagePath);
        QVERIFY(language.open(QIODevice::WriteOnly));
        language.write("da\n"); language.close();
        QTRY_COMPARE(translator.language(), QString("da"));
        QTRY_COMPARE(window->title(), QString::fromUtf8("Marionette-dukkeforhåndsvisning"));
        QTest::qWait(100);
        QVERIFY(!window->grabWindow().isNull());
        window->grabWindow().save(temporary.filePath("danish.png"));
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
