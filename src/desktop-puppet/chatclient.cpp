#include "chatclient.h"
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonDocument>
#include <QJsonObject>

ChatClient::ChatClient(const QString &dataDirectory, QObject *parent)
    : QObject(parent), m_directory(QDir(dataDirectory).absolutePath()) {
    m_monitor.setInterval(500);
    connect(&m_monitor, &QTimer::timeout, this, &ChatClient::refreshSession);
    m_connectTimeout.setSingleShot(true);
    m_connectTimeout.setInterval(5000);
    connect(&m_connectTimeout, &QTimer::timeout, this, [this] {
        fail(tr("Could not connect. Start the main chat and try again."));
    });
    connect(&m_socket, &QLocalSocket::connected, this, [this] {
        m_connectTimeout.stop();
        if (m_socket.write(m_request) < 0)
            fail(tr("Could not send the message. Check the main chat."));
        m_request.clear();
    });
    connect(&m_socket, &QLocalSocket::readyRead, this, &ChatClient::receive);
    connect(&m_socket, &QLocalSocket::errorOccurred, this, [this] {
        // A peer may send its complete reply immediately before closing.
        receive();
        if (m_busy) fail(tr("Chat disconnected. Check the main chat before sending again."));
    });
    connect(&m_socket, &QLocalSocket::disconnected, this, [this] {
        receive();
        if (m_busy) fail(tr("Chat disconnected. Check the main chat before sending again."));
    });
    refreshSession();
    m_monitor.start();
}

void ChatClient::refreshSession() {
    QFile descriptor(m_directory + "/session/log-session.json");
    QJsonObject info;
    if (descriptor.open(QIODevice::ReadOnly) && descriptor.size() <= 16384)
        info = QJsonDocument::fromJson(descriptor.readAll()).object();
    const QString session = info.value("session").toString();
    const QString generation = info.value("generation").toString();
    const QFileInfo resetGuard(m_directory + "/memory-reset-incomplete.json");
    const bool blocked = resetGuard.exists() || resetGuard.isSymLink();
    if (session != m_session || generation != m_generation || (blocked && !m_blocked)) {
        // Reset clears the view even when initiated by another interface. Keep an
        // in-flight reset request alive so its final acknowledgment can be shown.
        m_reply.clear();
        m_error.clear();
        if (session != m_session && m_busy) stopRequest();
        m_session = session;
        m_generation = generation;
        emit cleared();
        emit changed();
    }
    m_blocked = blocked;
}

bool ChatClient::send(const QString &text) {
    if (m_busy || text.trimmed().isEmpty()) return false;
    if (text.trimmed() == "/exit") { emit closeRequested(); return true; }
    refreshSession();
    m_error.clear();
    if (m_session.isEmpty() || m_blocked) {
        fail(m_blocked ? tr("Memory reset is incomplete. Finish recovery before chatting.")
                       : tr("Start Marionette's main chat, select a profile, then send your message."));
        return false;
    }
    m_requestGeneration = m_generation;
    m_request = QJsonDocument(QJsonObject{{"source", "desktop"}, {"message", text},
        {"session", m_session}, {"generation", m_generation}}).toJson(QJsonDocument::Compact) + '\n';
    if (m_request.size() > 1024 * 1024) {
        fail(tr("Message is too long. Shorten it and try again."));
        return false;
    }
    m_response.clear();
    m_busy = true;
    emit changed();
    m_connectTimeout.start();
    m_socket.connectToServer(m_directory + "/session/chat.sock");
    return true;
}

void ChatClient::receive() {
    if (!m_busy) return;
    if (m_socket.bytesAvailable()) m_response += m_socket.readAll();
    if (m_response.size() > 4 * 1024 * 1024) {
        fail(tr("Chat returned an oversized reply. Check the main chat."));
        return;
    }
    const auto end = m_response.indexOf('\n');
    if (end < 0) return;
    QJsonParseError parse;
    const auto document = QJsonDocument::fromJson(m_response.left(end), &parse);
    const auto result = document.object();
    refreshSession();
    if (!m_busy) return; // The model session was stopped or replaced.
    if (parse.error != QJsonParseError::NoError || !document.isObject()) {
        fail(tr("Chat returned an invalid reply. Check the main chat."));
        return;
    }
    if (result.contains("error")) {
        fail(tr("Chat could not finish this message. Check the main chat before retrying."));
        return;
    }
    if (m_blocked || result.value("session").toString() != m_session ||
        result.value("generation").toString() != m_generation ||
        (m_requestGeneration != m_generation && result.value("finish").toString() != "resetmemory")) {
        stopRequest();
        m_reply.clear();
        emit cleared();
        emit changed();
        return;
    }
    if (!result.value("answer").isString() || !result.value("finish").isString() ||
        !result.value("generation").isString() || !result.value("session").isString()) {
        fail(tr("Chat returned an invalid reply. Check the main chat."));
        return;
    }
    m_reply = result.value("answer").toString();
    if (result.value("finish").toString() == "length")
        m_reply += tr("\n\n[Reply reached its length limit.]");
    stopRequest();
    emit answered();
    emit changed();
}

void ChatClient::stopRequest() {
    m_busy = false;
    m_connectTimeout.stop();
    m_request.clear();
    m_response.clear();
    m_socket.abort();
}

void ChatClient::fail(const QString &message) {
    stopRequest();
    m_error = message;
    emit changed();
}

void ChatClient::dismiss() {
    m_reply.clear();
    m_error.clear();
    emit changed();
}
