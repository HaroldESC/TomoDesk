"""Diálogo de Memorias: lectura completa, datos sucios y borrado confirmado.

Cubre la jerarquía de botones (Design.md §2.1) y la Ola 1 de la Fase 3:
panel de detalle, tolerancia a datos invalidos, estado vacio y confirmacion.
"""

import datetime

import pytest
from PySide6.QtCore import QLocale, Qt
from PySide6.QtWidgets import QMessageBox, QPushButton


@pytest.fixture(autouse=True)
def ensure_qapp(qapp):
    return qapp


@pytest.fixture
def mock_memory_manager():
    from unittest.mock import MagicMock

    return MagicMock()


def _button_with_text(box, text):
    """Botón del QMessageBox con esa etiqueta (``addButton``, no StandardButton)."""
    return next(b for b in box.buttons() if b.text() == text)


@pytest.fixture(autouse=True)
def no_blocking_message_box(monkeypatch):
    """Ningun test puede abrir un QMessageBox modal real: la suite se colgaria."""
    def fake_exec(self):
        return 0

    monkeypatch.setattr(QMessageBox, "exec", fake_exec)
    monkeypatch.setattr(
        QMessageBox,
        "clickedButton",
        lambda self: _button_with_text(self, "dialogs.confirm.accept"),
    )


@pytest.fixture
def answer(monkeypatch):
    """Fuerza la respuesta del dialogo de confirmacion y captura los boxes."""
    def _answer(accept: bool) -> list:
        key = "dialogs.confirm.accept" if accept else "dialogs.confirm.cancel"
        boxes = []

        def fake_exec(self):
            boxes.append(self)
            return 0

        monkeypatch.setattr(QMessageBox, "exec", fake_exec)
        monkeypatch.setattr(
            QMessageBox,
            "clickedButton",
            lambda self: _button_with_text(self, key),
        )
        return boxes

    return _answer


def _memory(**overrides) -> dict:
    """Memoria episodica con la forma que devuelve ``list_episodic_log``."""
    data = {
        "id": 1,
        "timestamp": "2026-01-02 03:04:05",
        "summary": "El usuario empezo un proyecto nuevo",
        "importance_score": 0.8,
        "source": "manual",
        "chroma_id": "doc-1",
    }
    data.update(overrides)
    return data


@pytest.fixture
def dialog(qtbot, mock_memory_manager, mock_i18n):
    mock_memory_manager.list_episodic_log.return_value = []
    from src.gui.windows.memories_dialog import MemoriesDialog

    widget = MemoriesDialog(mock_memory_manager, i18n=mock_i18n)
    qtbot.addWidget(widget)
    return widget


@pytest.fixture
def make_dialog(qtbot, mock_memory_manager, mock_i18n):
    """Construye el diálogo con una lista de memorias concreta."""
    def _make(memories) -> object:
        mock_memory_manager.list_episodic_log.return_value = memories
        from src.gui.windows.memories_dialog import MemoriesDialog

        widget = MemoriesDialog(mock_memory_manager, i18n=mock_i18n)
        qtbot.addWidget(widget)
        return widget

    return _make


def _buttons(dialog):
    return {b.text(): b.objectName() for b in dialog.findChildren(QPushButton)}


class TestButtonHierarchy:
    """``Design.md`` §2.1: un objectName por rol."""

    def test_delete_is_danger_and_refresh_is_flat(self, dialog):
        roles = _buttons(dialog)
        assert roles["dialogs.memories.delete"] == "danger"
        assert roles["dialogs.memories.refresh"] == "flat"
        # No hay accion primaria en este dialogo: solo utilidad y destruccion.
        assert set(roles.values()) == {"danger", "flat"}

    def test_every_button_uses_a_known_variant(self, dialog):
        assert set(_buttons(dialog).values()) <= {"danger", "flat"}


class TestDetailPanel:
    """Una memoria se lee entera en el panel derecho, no en una linea de 70."""

    def test_list_and_detail_are_side_by_side(self, dialog):
        assert dialog.splitter.orientation() == Qt.Orientation.Horizontal
        assert dialog.splitter.count() == 2
        assert dialog.splitter.widget(1) is dialog.detail_view
        # El listado (con su estado vacío) vive en el panel izquierdo.
        assert dialog.splitter.widget(0).isAncestorOf(dialog.memory_list)
        assert dialog.memory_list.minimumWidth() >= 260

    def test_detail_is_read_only_and_frameless(self, dialog):
        from PySide6.QtWidgets import QFrame

        assert dialog.detail_view.isReadOnly() is True
        assert dialog.detail_view.frameShape() == QFrame.Shape.NoFrame

    def test_minimum_size_is_the_design_one(self, dialog):
        assert dialog.minimumWidth() == 500
        assert dialog.minimumHeight() == 360

    def test_detail_shows_the_whole_summary(self, make_dialog):
        summary = "L" * 200
        dialog = make_dialog([_memory(summary=summary)])

        assert summary in dialog.detail_view.toPlainText()

    def test_list_item_summary_is_truncated_with_ellipsis(self, make_dialog):
        summary = "M" * 120
        dialog = make_dialog([_memory(summary=summary)])

        kwargs = _memory_item_kwargs(dialog)
        assert kwargs["summary"] == "M" * 70 + "..."
        # El detalle sigue enseñando el resumen entero.
        assert summary in dialog.detail_view.toPlainText()

    def test_tooltip_carries_the_full_summary(self, make_dialog):
        summary = "T" * 200
        dialog = make_dialog([_memory(summary=summary)])

        assert dialog.memory_list.item(0).toolTip() == summary

    def test_short_summary_is_not_truncated(self, make_dialog):
        dialog = make_dialog([_memory(summary="corta")])

        assert _memory_item_kwargs(dialog)["summary"] == "corta"

    def test_header_has_stars_source_and_date(self, make_dialog):
        dialog = make_dialog([_memory()])
        detail = dialog.detail_view.toPlainText()
        header = detail.split("\n")[0]

        assert "\u2605" * 4 in header  # 0.8 * 5
        assert "manual" in header
        expected = QLocale.system().toString(
            datetime.datetime.fromisoformat("2026-01-02 03:04:05"),
            QLocale.FormatType.ShortFormat,
        )
        assert expected in header

    def test_summary_is_separated_from_the_header_by_a_blank_line(
        self, make_dialog
    ):
        dialog = make_dialog([_memory()])

        header, _, body = dialog.detail_view.toPlainText().partition("\n")
        assert header.strip()
        assert body.strip() == "El usuario empezo un proyecto nuevo"

    def test_detail_is_plain_text_never_html(self, make_dialog):
        """El resumen viene de la base de datos: no se interpreta como HTML."""
        dialog = make_dialog([_memory(summary="<b>inyectado</b> <script>x</script>")])

        detail = dialog.detail_view.toPlainText()
        assert "<b>inyectado</b>" in detail
        assert "<script>x</script>" in detail

    def test_selecting_another_row_updates_the_detail(self, make_dialog):
        dialog = make_dialog([_memory(id=1), _memory(id=2, summary="la segunda")])

        dialog.memory_list.setCurrentRow(1)

        assert "la segunda" in dialog.detail_view.toPlainText()

    def test_unparseable_timestamp_is_shown_verbatim(self, make_dialog):
        dialog = make_dialog([_memory(timestamp="cuando sea")])

        assert "cuando sea" in dialog.detail_view.toPlainText()

    def test_missing_timestamp_leaves_the_header_clean(self, make_dialog):
        dialog = make_dialog([_memory(timestamp=None)])

        header = dialog.detail_view.toPlainText().split("\n")[0]
        assert "None" not in header
        assert header.strip() == "\u2605" * 4 + " \u00b7 manual"

class TestMessyData:
    """``importance_score`` es un REAL que puede venir vacio o como texto."""

    @pytest.mark.parametrize(
        "score, stars",
        [
            (None, 0),
            ("0.8", 4),
            (1.0, 5),
            (0.0, 0),
            (-1.0, 0),
            ("no es un numero", 0),
            (42.0, 5),
        ],
    )
    def test_importance_score_never_raises(
        self, make_dialog, mock_i18n, score, stars
    ):
        dialog = make_dialog([_memory(importance_score=score)])

        assert _memory_item_kwargs(dialog)["stars"] == "\u2605" * stars

    def test_memory_without_source_does_not_raise(self, make_dialog):
        dialog = make_dialog([_memory(source=None)])

        assert _memory_item_kwargs(dialog)["source"] == ""

    def test_memory_without_id_does_not_raise(self, make_dialog):
        data = _memory()
        del data["id"]
        dialog = make_dialog([data])

        assert dialog.memory_list.count() == 1


class TestEmptyAndSelection:
    """El detalle nunca ensena la memoria anterior por descuido."""

    def test_empty_list_shows_the_empty_label(self, dialog):
        assert dialog.empty_label.text() == "dialogs.memories.empty"
        assert dialog.empty_label.isVisibleTo(dialog) is True
        assert dialog.memory_list.isVisibleTo(dialog) is False

    def test_empty_list_leaves_the_detail_blank(self, dialog):
        assert dialog.detail_view.toPlainText() == ""

    def test_non_empty_list_hides_the_empty_label(self, make_dialog):
        dialog = make_dialog([_memory()])

        assert dialog.empty_label.isVisibleTo(dialog) is False
        assert dialog.memory_list.isVisibleTo(dialog) is True

    def test_no_selection_shows_the_hint(self, make_dialog):
        dialog = make_dialog([_memory()])

        dialog.memory_list.setCurrentRow(-1)

        assert (
            dialog.detail_view.toPlainText()
            == "dialogs.memories.no_selection"
        )

    def test_refresh_after_emptying_the_store_clears_the_detail(
        self, make_dialog, mock_memory_manager
    ):
        dialog = make_dialog([_memory()])
        assert dialog.detail_view.toPlainText() != ""

        mock_memory_manager.list_episodic_log.return_value = []
        dialog._load_memories()

        assert dialog.detail_view.toPlainText() == ""

    def test_refresh_selects_the_first_memory_automatically(self, make_dialog):
        dialog = make_dialog([_memory(), _memory(id=2, summary="la segunda")])

        assert dialog.memory_list.currentRow() == 0
        assert "la segunda" not in dialog.detail_view.toPlainText()


class TestDeleteConfirmation:
    """Borrar una memoria es destructivo: siempre se pregunta."""

    def test_declining_does_not_delete(self, make_dialog, mock_memory_manager, answer):
        dialog = make_dialog([_memory()])
        answer(False)

        dialog._delete_memory()

        mock_memory_manager.delete_episodic_memory.assert_not_called()
        assert dialog.memory_list.count() == 1

    def test_accepting_deletes_and_refreshes(
        self, make_dialog, mock_memory_manager, answer
    ):
        dialog = make_dialog([_memory()])
        answer(True)

        dialog._delete_memory()

        mock_memory_manager.delete_episodic_memory.assert_called_once_with(1)
        # La lista se recarga para que el item desaparezca.
        assert mock_memory_manager.list_episodic_log.call_count == 2

    def test_prompt_uses_the_memory_keys(self, make_dialog, answer):
        dialog = make_dialog([_memory()])
        boxes = answer(False)

        dialog._delete_memory()

        assert len(boxes) == 1
        assert boxes[0].windowTitle() == "dialogs.memories.delete_confirm_title"
        assert boxes[0].text() == "dialogs.memories.delete_confirm_body"

    def test_without_selection_nothing_happens(
        self, make_dialog, mock_memory_manager, answer
    ):
        dialog = make_dialog([_memory()])
        answer(True)
        dialog.memory_list.setCurrentRow(-1)

        dialog._delete_memory()

        mock_memory_manager.delete_episodic_memory.assert_not_called()

    def test_button_click_goes_through_the_confirmation(
        self, qtbot, make_dialog, mock_memory_manager, answer
    ):
        dialog = make_dialog([_memory()])
        answer(False)

        qtbot.mouseClick(dialog.delete_btn, Qt.MouseButton.LeftButton)

        mock_memory_manager.delete_episodic_memory.assert_not_called()


def _memory_item_kwargs(dialog) -> dict:
    """Argumentos de la última llamada a ``i18n.t`` de tipo ``memory_item``."""
    for call in reversed(dialog.i18n.t.call_args_list):
        if call.args and call.args[0] == "commands.memory_item":
            return call.kwargs
    raise AssertionError("no se pidio ninguna etiqueta commands.memory_item")
