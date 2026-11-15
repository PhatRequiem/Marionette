#include <QGuiApplication>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QQuickStyle>
#include <QQuickWindow>
#include <QScreen>
#include <QTimer>
#include <QLockFile>
#include <QStandardPaths>
#include <QDir>
#include <QDebug>
#include <LayerShellQt/window.h>
#include "backend.h"
#include "chatclient.h"
#include "replypresentation.h"
#include "theme.h"
#include "translator.h"

int main(int argc, char **argv) {
    QQuickWindow::setDefaultAlphaBuffer(true);
    QGuiApplication app(argc, argv);
    app.setApplicationName("marionette-puppet");
    app.setApplicationVersion("0.3.0");
    app.setDesktopFileName("marionette-puppet");
    const bool preview = app.arguments().contains("--preview");
    if (!preview && app.platformName() != "wayland") {
        qCritical() << "Desktop mode requires Wayland with wlr-layer-shell. Use --preview for a normal window.";
        return 1;
    }
    QLockFile lock(QStandardPaths::writableLocation(QStandardPaths::RuntimeLocation) + "/marionette-puppet.lock");
    if (!preview && !lock.tryLock(0)) {
        qCritical() << "Marionette puppet is already running, or the runtime lock is unavailable.";
        return 1;
    }
    QQuickStyle::setStyle("Material");
    qmlRegisterType<ReplyPresentation>("Marionette", 1, 0, "ReplyPresentation");
    Translator translator;
    app.installTranslator(&translator);
    Theme theme;
    Backend backend;
    // The binary lives in runtime/desktop-puppet; launchers may override the data root.
    const auto data = qEnvironmentVariable("MARIONETTE_DATA_DIR",
        QDir(app.applicationDirPath()).absoluteFilePath("../../data"));
    ChatClient chat(data);
    QQmlApplicationEngine engine;
    QObject::connect(&translator, &Translator::changed, &engine, &QQmlEngine::retranslate);
    engine.rootContext()->setContextProperty("theme", &theme);
    engine.rootContext()->setContextProperty("translator", &translator);
    engine.rootContext()->setContextProperty("backend", &backend);
    engine.rootContext()->setContextProperty("chat", &chat);
    engine.rootContext()->setContextProperty("previewMode", preview);
    engine.load(QUrl("qrc:/Main.qml"));
    if (engine.rootObjects().isEmpty()) return 1;
    auto *window = qobject_cast<QQuickWindow *>(engine.rootObjects().first());
    if (!window) return 1;
    backend.setWindow(window);
    if (!preview) {
        auto *layer = LayerShellQt::Window::get(window);
        layer->setScope("marionette-puppet");
        layer->setLayer(LayerShellQt::Window::LayerTop);
        layer->setAnchors(LayerShellQt::Window::Anchors(LayerShellQt::Window::AnchorTop) | LayerShellQt::Window::AnchorBottom |
                          LayerShellQt::Window::AnchorLeft | LayerShellQt::Window::AnchorRight);
        layer->setExclusiveZone(-1);
        layer->setKeyboardInteractivity(LayerShellQt::Window::KeyboardInteractivityOnDemand);
        layer->setActivateOnShow(false);
        layer->setCloseOnDismissed(true);
        window->resize(window->screen()->size());
    }
    window->show();
    QMetaObject::invokeMethod(window, "placeInitial");
    // Bounded smoke runs exercise the same QML without leaving another companion.
    const int smoke = app.arguments().indexOf("--smoke");
    if (smoke >= 0) {
        QTimer::singleShot(1200, &app, [&] {
            const auto frame = window->grabWindow();
            if (frame.isNull()) { app.exit(2); return; }
            if (smoke + 1 < app.arguments().size() && !frame.save(app.arguments().at(smoke + 1))) {
                app.exit(3); return;
            }
            app.quit();
        });
    }
    return app.exec();
}
