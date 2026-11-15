#pragma once
#include <QObject>
#include <QQuickWindow>

class Backend : public QObject {
    Q_OBJECT
public:
    explicit Backend(QObject *parent = nullptr) : QObject(parent) {}
    void setWindow(QQuickWindow *window) { m_window = window; }
    Q_INVOKABLE void inputAreas(const QRectF &body, const QRectF &bubble);
private:
    QQuickWindow *m_window = nullptr;
};
