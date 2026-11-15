#pragma once
#include <QObject>
#include <QLocalSocket>
#include <QTimer>

// A presentation-only client. Profiles, tools and durable messages stay in Python.
class ChatClient : public QObject {
    Q_OBJECT
    Q_PROPERTY(bool busy READ busy NOTIFY changed)
    Q_PROPERTY(QString reply READ reply NOTIFY changed)
    Q_PROPERTY(QString error READ error NOTIFY changed)
public:
    explicit ChatClient(const QString &dataDirectory, QObject *parent = nullptr);
    bool busy() const { return m_busy; }
    QString reply() const { return m_reply; }
    QString error() const { return m_error; }
    Q_INVOKABLE bool send(const QString &text);
    Q_INVOKABLE void dismiss();
signals:
    void changed();
    void cleared();
    void answered();
    void closeRequested();
private:
    void refreshSession();
    void receive();
    void fail(const QString &message);
    void stopRequest();
    QString m_directory, m_session, m_generation, m_requestGeneration;
    QString m_reply, m_error;
    QByteArray m_request, m_response;
    bool m_busy = false, m_blocked = false;
    QLocalSocket m_socket;
    QTimer m_monitor, m_connectTimeout;
};
