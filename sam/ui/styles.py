APP_STYLESHEET = """
QMainWindow {
    background: #f1f5f9;
}
QWidget {
    font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
    color: #0f172a;
}
QLabel#appTitle {
    font-size: 18px;
    font-weight: 600;
    color: #0f172a;
}
QLabel#sectionTitle {
    font-size: 14px;
    font-weight: 600;
    color: #1e293b;
    padding-top: 4px;
}
QLabel#sectionHint {
    font-size: 12px;
    color: #64748b;
    padding-bottom: 6px;
}
QLabel#pathLabel {
    font-family: Consolas, "Cascadia Mono", monospace;
    font-size: 11px;
    color: #334155;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 4px;
    padding: 6px 8px;
}
QLabel#hintLabel {
    color: #64748b;
    font-size: 12px;
}
QLabel#statusOk {
    color: #15803d;
    font-weight: 500;
}
QLabel#statusWarn {
    color: #b45309;
    font-weight: 500;
}
QTabWidget::pane {
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    background: #ffffff;
    top: -1px;
    padding: 4px;
}
QTabBar::tab {
    background: #e2e8f0;
    color: #475569;
    border: 1px solid #cbd5e1;
    border-bottom: none;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    padding: 10px 20px;
    margin-right: 4px;
    min-width: 100px;
}
QTabBar::tab:selected {
    background: #ffffff;
    color: #0f172a;
    font-weight: 600;
    border-bottom: 2px solid #2563eb;
}
QTabBar::tab:hover:!selected {
    background: #f1f5f9;
}
QGroupBox {
    font-weight: 600;
    font-size: 13px;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    margin-top: 12px;
    padding: 12px 14px 14px 14px;
    background: #ffffff;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #2563eb;
}
QPushButton {
    background: #2563eb;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 8px 18px;
    font-weight: 600;
    min-height: 28px;
}
QPushButton:hover { background: #1d4ed8; }
QPushButton:pressed { background: #1e40af; }
QPushButton:disabled { background: #cbd5e1; color: #f1f5f9; }
QPushButton#primaryLarge {
    min-height: 36px;
    font-size: 14px;
    padding: 10px 24px;
}
QPushButton#secondaryBtn {
    background: #ffffff;
    color: #334155;
    border: 1px solid #cbd5e1;
    font-weight: 500;
}
QPushButton#secondaryBtn:hover { background: #f8fafc; }
QPushButton#stopBtn {
    background: #dc2626;
}
QPushButton#stopBtn:hover { background: #b91c1c; }
QLineEdit, QDateEdit, QComboBox {
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 6px 10px;
    background: #ffffff;
    min-height: 28px;
}
QLineEdit:focus, QDateEdit:focus, QComboBox:focus {
    border: 1px solid #2563eb;
}
QCheckBox {
    spacing: 8px;
}
QTextEdit#logView {
    background: #0f172a;
    color: #e2e8f0;
    border-radius: 8px;
    font-family: Consolas, monospace;
    font-size: 12px;
    border: none;
    padding: 8px;
}
QScrollArea {
    border: none;
    background: transparent;
}
"""
