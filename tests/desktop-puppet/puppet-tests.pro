QT += core gui qml quick quickcontrols2 testlib
CONFIG += c++17 testcase
TARGET = puppet-tests
SOURCES += puppet-tests.cpp ../../src/desktop-puppet/backend.cpp ../../src/desktop-puppet/theme.cpp ../../src/desktop-puppet/translator.cpp
HEADERS += ../../src/desktop-puppet/backend.h ../../src/desktop-puppet/theme.h ../../src/desktop-puppet/translator.h
INCLUDEPATH += ../../src/desktop-puppet
RESOURCES += ../../src/desktop-puppet/resources.qrc
