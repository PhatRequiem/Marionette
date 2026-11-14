#pragma once
#include <QObject>
#include <QQuickWindow>

class Backend : public QObject {
    Q_OBJECT
public:
    explicit Backend(QObject *parent = nullptr) : QObject(parent) {}
    void setWindow(QQuickWindow *window) { m_window = window; }
    Q_INVOKABLE void inputArea(qreal x, qreal y, qreal width, qreal height);
private:
    QQuickWindow *m_window = nullptr;
};
