"""Visual style: one accent colour, soft grey background, white cards."""

ACCENT = "#1F4E9B"
ACCENT_DARK = "#173B76"
BG = "#F3F5F9"
CARD = "#FFFFFF"
INK = "#1D2433"
MUTED = "#5B6475"
LINE = "#DDE2EA"
GREEN = "#107C41"
AMBER = "#B7791F"
RED = "#C0392B"
GREY = "#7A8291"

STATE_COLORS = {
    "AVAILABLE": GREEN, "PARTIALLY_ALLOCATED": AMBER, "FULLY_ALLOCATED": ACCENT,
    "EXPIRED": RED, "DISABLED": GREY, "COMPLETED": GREEN, "CANCELLED": RED,
    "ISSUED": GREEN, "VOID": RED, "ALLOCATED": AMBER, "CONFIRMED": GREEN,
    "RELEASED": GREY, "CONSUMED": RED,
}

STYLESHEET = f"""
QWidget {{ font-size: 13px; color: {INK}; }}
QMainWindow, QStackedWidget, QScrollArea, QScrollArea > QWidget > QWidget {{ background: {BG}; }}
QDialog {{ background: {BG}; }}
#Sidebar {{ background: #14284B; }}
#Sidebar QLabel {{ color: white; }}
#SidebarTitle {{ font-size: 17px; font-weight: 700; }}
#SidebarSub {{ color: #A9B8D6; font-size: 11px; }}
#Sidebar QListWidget {{ background: transparent; border: none; color: #DCE4F2; outline: none; }}
#Sidebar QListWidget::item {{ padding: 9px 12px; border-radius: 6px; margin: 1px 8px; }}
#Sidebar QListWidget::item:selected {{ background: {ACCENT}; color: white; }}
#Sidebar QListWidget::item:hover:!selected {{ background: rgba(255,255,255,0.08); }}
#Sidebar QPushButton {{ background: rgba(255,255,255,0.1); color: white; border: none; padding: 7px; border-radius: 6px; }}
#PageTitle {{ font-size: 21px; font-weight: 700; }}
#PageSubtitle {{ color: {MUTED}; }}
#Card {{ background: {CARD}; border: 1px solid {LINE}; border-radius: 10px; }}
#CardTitle {{ font-weight: 700; font-size: 14px; }}
#StatValue {{ font-size: 22px; font-weight: 700; }}
#StatLabel {{ color: {MUTED}; font-size: 12px; }}
#Muted {{ color: {MUTED}; }}
#Warning {{ color: {AMBER}; }}
#Danger {{ color: {RED}; }}
#KeyLabel {{ font-family: Menlo, Consolas, monospace; font-size: 15px; font-weight: 600; }}
QPushButton {{ background: white; border: 1px solid {LINE}; border-radius: 6px; padding: 6px 14px; }}
QPushButton:hover {{ border-color: {ACCENT}; }}
QPushButton:disabled {{ color: #A0A7B4; }}
QPushButton#Primary {{ background: {ACCENT}; color: white; border: 1px solid {ACCENT}; font-weight: 600; }}
QPushButton#Primary:hover {{ background: {ACCENT_DARK}; }}
QPushButton#Danger {{ color: {RED}; }}
QLineEdit, QComboBox, QSpinBox, QDateEdit, QPlainTextEdit, QTextEdit, QDoubleSpinBox {{
    background: white; border: 1px solid {LINE}; border-radius: 6px; padding: 5px 7px; }}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDateEdit:disabled {{ background: #EEF1F5; color: #8A93A3; }}
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus, QSpinBox:focus, QDateEdit:focus {{ border-color: {ACCENT}; }}
QTableView {{ background: white; border: 1px solid {LINE}; border-radius: 8px; gridline-color: #EEF1F5;
    selection-background-color: #DCE7F8; selection-color: {INK}; alternate-background-color: #FAFBFD; }}
QHeaderView::section {{ background: #F7F8FB; border: none; border-bottom: 1px solid {LINE};
    padding: 6px; font-weight: 600; color: {MUTED}; }}
QTabWidget::pane {{ border: 1px solid {LINE}; border-radius: 8px; background: white; top: -1px; }}
QTabBar::tab {{ padding: 7px 14px; }}
QTabBar::tab:selected {{ color: {ACCENT}; font-weight: 600; }}
QListWidget#Plain {{ background: white; border: 1px solid {LINE}; border-radius: 8px; }}
QGroupBox {{ background: white; border: 1px solid {LINE}; border-radius: 8px; margin-top: 14px; padding: 10px; font-weight: 600; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; }}
"""
