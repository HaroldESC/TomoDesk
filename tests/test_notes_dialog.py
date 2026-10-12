"""Diálogo de Notas: editor usable, aviso de cambios y borrado confirmado.

Cubre la jerarquía de botones (Design.md §2.1) y la Ola 1 de la Fase 3:
editor sin tope de altura, cambios sin guardar y confirmaciones.
"""

import pytest
from PySide6.QtWidgets import QMessageBox, QPushButton, QScrollArea


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
    """Ningun test puede abrir un QMessageBox modal real: la suite se colgaria.

    Por defecto se responde "confirmar"; los tests que scenifican el "no"
    reescriben la respuesta con el fixture ``answer``.
    """
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


def _note(note_id: int, title: str = "", content: str = "") -> dict:
    return {"id": note_id, "title": title, "content": content}


@pytest.fixture
def dialog(qtbot, mock_memory_manager, mock_i18n):
    mock_memory_manager.list_notes.return_value = []
    from src.gui.windows.notes_dialog import NotesDialog

    widget = NotesDialog(mock_memory_manager, i18n=mock_i18n)
    qtbot.addWidget(widget)
    return widget


@pytest.fixture
def make_dialog(qtbot, mock_memory_manager, mock_i18n):
    """Construye el diálogo con una lista de notas concreta."""
    def _make(notes) -> object:
        mock_memory_manager.list_notes.return_value = notes
        from src.gui.windows.notes_dialog import NotesDialog

        widget = NotesDialog(mock_memory_manager, i18n=mock_i18n)
        qtbot.addWidget(widget)
        return widget

    return _make


@pytest.fixture
def two_notes(make_dialog):
    """Diálogo con dos notas: la 0 es la más reciente."""
    return make_dialog([
        _note(2, "segunda", "contenido dos"),
        _note(1, "primera", "contenido uno"),
    ])


def _buttons(dialog):
    return {b.text(): b.objectName() for b in dialog.findChildren(QPushButton)}


class TestButtonHierarchy:
    """``Design.md`` §2.1: un objectName por rol."""

    def test_save_is_the_only_primary(self, dialog):
        """Guardar no lleva objectName; el resto usa una variante conocida."""
        roles = _buttons(dialog)
        assert roles["dialogs.notes.save"] == ""
        assert roles["dialogs.notes.delete"] == "danger"
        assert roles["dialogs.notes.new"] == "secondary"
        assert set(roles.values()) <= {"", "danger", "secondary"}

    def test_delete_is_destructive_and_new_is_secondary(self, dialog):
        roles = _buttons(dialog)
        assert roles["dialogs.notes.delete"] == "danger"
        assert roles["dialogs.notes.new"] == "secondary"

    def test_every_button_uses_a_known_variant(self, dialog):
        assert set(_buttons(dialog).values()) <= {"", "danger", "secondary"}


class TestEditorLayout:
    """El caso real es escribir texto largo: el editor no puede estar encajonado."""

    def test_content_editor_has_no_height_cap(self, dialog):
        assert dialog.content_input.maximumHeight() != 100
        assert dialog.content_input.maximumHeight() > 100

    def test_content_editor_has_a_usable_minimum_height(self, dialog):
        assert dialog.content_input.minimumHeight() >= 150

    def test_form_lives_in_a_scroll_area(self, dialog):
        assert isinstance(dialog.scroll, QScrollArea)
        assert dialog.scroll.widgetResizable() is True
        assert dialog.scroll.isAncestorOf(dialog.title_input)
        assert dialog.scroll.isAncestorOf(dialog.content_input)

    def test_dialog_keeps_the_design_minimum_and_grows_on_open(self, dialog):
        assert dialog.minimumWidth() == 500
        assert dialog.minimumHeight() == 360
        assert (dialog.width(), dialog.height()) == (560, 560)

    def test_selecting_a_note_loads_it_in_the_editor(self, two_notes):
        two_notes.note_list.setCurrentRow(0)

        assert two_notes.title_input.text() == "segunda"
        assert two_notes.content_input.toPlainText() == "contenido dos"


class TestDirtyTracking:
    """``_dirty`` distingue lo que el usuario escribió de lo que se cargó."""

    def test_starts_clean(self, two_notes):
        assert two_notes._dirty is False

    def test_selecting_a_note_does_not_dirty_the_dialog(self, two_notes):
        two_notes.note_list.setCurrentRow(0)

        assert two_notes._dirty is False

    def test_typing_dirties_the_dialog(self, two_notes):
        two_notes.note_list.setCurrentRow(0)

        two_notes.content_input.setPlainText("otro texto")

        assert two_notes._dirty is True

    def test_saving_clears_dirty_and_keeps_the_row(
        self, two_notes, mock_memory_manager
    ):
        two_notes.note_list.setCurrentRow(0)
        two_notes.content_input.setPlainText("contenido dos editado")
        assert two_notes._dirty is True

        two_notes._save_note()

        mock_memory_manager.update_note.assert_called_once_with(
            2, title="segunda", content="contenido dos editado"
        )
        assert two_notes._dirty is False
        assert two_notes._current_row == 0
        assert two_notes.note_list.currentRow() == 0

    def test_loading_a_note_after_saving_shows_the_stored_content(
        self, two_notes, mock_memory_manager
    ):
        """Tras guardar, el editor se recarga desde la lista y queda limpio."""
        mock_memory_manager.list_notes.return_value = [
            _note(2, "segunda", "contenido dos editado"),
            _note(1, "primera", "contenido uno"),
        ]
        two_notes.note_list.setCurrentRow(0)
        two_notes.content_input.setPlainText("contenido dos editado")

        two_notes._save_note()

        assert two_notes.content_input.toPlainText() == "contenido dos editado"
        assert two_notes._dirty is False

    def test_saving_without_title_does_nothing(self, dialog, mock_memory_manager):
        dialog.title_input.setText("   ")
        dialog.content_input.setPlainText("sin titulo")

        dialog._save_note()

        mock_memory_manager.add_note.assert_not_called()
        mock_memory_manager.update_note.assert_not_called()


class TestSwitchingNotes:
    """Cambiar de nota no descarta lo escrito sin preguntar."""

    def test_declining_keeps_the_previous_note_and_the_text(
        self, two_notes, answer
    ):
        answer(False)
        two_notes.note_list.setCurrentRow(0)
        two_notes.content_input.setPlainText("cambio sin guardar")

        two_notes.note_list.setCurrentRow(1)

        assert two_notes.note_list.currentRow() == 0
        assert two_notes.content_input.toPlainText() == "cambio sin guardar"
        assert two_notes.title_input.text() == "segunda"
        assert two_notes._dirty is True

    def test_accepting_switches_and_discards(self, two_notes, answer):
        answer(True)
        two_notes.note_list.setCurrentRow(0)
        two_notes.content_input.setPlainText("cambio sin guardar")

        two_notes.note_list.setCurrentRow(1)

        assert two_notes.note_list.currentRow() == 1
        assert two_notes.content_input.toPlainText() == "contenido uno"
        assert two_notes.title_input.text() == "primera"
        assert two_notes._dirty is False

    def test_clean_dialog_switches_without_asking(self, two_notes, answer):
        boxes = answer(False)
        two_notes.note_list.setCurrentRow(0)

        two_notes.note_list.setCurrentRow(1)

        assert boxes == []
        assert two_notes.content_input.toPlainText() == "contenido uno"

    def test_prompt_uses_the_notes_keys(self, two_notes, answer):
        boxes = answer(False)
        two_notes.note_list.setCurrentRow(0)
        two_notes.title_input.setText("editado")

        two_notes.note_list.setCurrentRow(1)

        assert len(boxes) == 1
        assert boxes[0].windowTitle() == "dialogs.notes.unsaved_title"
        assert boxes[0].text() == "dialogs.notes.unsaved_body"

    def test_selecting_the_same_row_asks_nothing(self, two_notes, answer):
        boxes = answer(False)
        two_notes.note_list.setCurrentRow(0)
        two_notes.title_input.setText("editado")

        two_notes._on_select(0)

        assert boxes == []
        assert two_notes._dirty is True


class TestNewNote:
    """``_new_note`` también respetar lo escrito."""

    def test_declining_keeps_the_note_and_the_text(self, two_notes, answer):
        answer(False)
        two_notes.note_list.setCurrentRow(0)
        two_notes.content_input.setPlainText("cambio sin guardar")

        two_notes._new_note()

        assert two_notes.note_list.currentRow() == 0
        assert two_notes.content_input.toPlainText() == "cambio sin guardar"
        assert two_notes._dirty is True

    def test_accepting_opens_a_blank_note(self, two_notes, answer):
        answer(True)
        two_notes.note_list.setCurrentRow(0)
        two_notes.content_input.setPlainText("cambio sin guardar")

        two_notes._new_note()

        assert two_notes.note_list.currentRow() == -1
        assert two_notes._current_row == -1
        assert two_notes.title_input.text() == ""
        assert two_notes.content_input.toPlainText() == ""
        assert two_notes._dirty is False

    def test_clean_dialog_asks_nothing(self, two_notes, answer):
        boxes = answer(False)
        two_notes.note_list.setCurrentRow(0)

        two_notes._new_note()

        assert boxes == []

    def test_saving_after_new_creates_a_note_instead_of_updating(
        self, two_notes, mock_memory_manager, answer
    ):
        """Regression: clearSelection() no vacía la fila actual."""
        answer(True)
        two_notes.note_list.setCurrentRow(0)

        two_notes._new_note()
        two_notes.title_input.setText("nota nueva")
        two_notes.content_input.setPlainText("contenido nuevo")
        two_notes._save_note()

        mock_memory_manager.add_note.assert_called_once_with(
            "nota nueva", "contenido nuevo"
        )
        mock_memory_manager.update_note.assert_not_called()


class TestClosingWithUnsavedChanges:
    """X, botón de cerrar y Esc pasan por ``closeEvent``/``reject()``."""

    def test_declining_keeps_the_dialog_open(self, two_notes, answer):
        answer(False)
        two_notes.title_input.setText("editado")
        two_notes.show()

        two_notes.close()

        assert two_notes.isVisible()
        two_notes._dirty = False  # no dejar el box abierto en el teardown

    def test_accepting_closes_the_dialog(self, two_notes, answer):
        answer(True)
        two_notes.title_input.setText("editado")
        two_notes.show()

        two_notes.close()

        assert not two_notes.isVisible()

    def test_closing_with_the_x_asks_only_once(self, two_notes, answer):
        """Regression: QDialog.closeEvent() llama a reject() por dentro."""
        boxes = answer(True)
        two_notes.title_input.setText("editado")
        two_notes.show()

        two_notes.close()

        assert len(boxes) == 1
        assert not two_notes.isVisible()

    def test_escape_asks_only_once(self, two_notes, answer):
        boxes = answer(True)
        two_notes.title_input.setText("editado")
        two_notes.show()

        two_notes.reject()

        assert len(boxes) == 1

    def test_escape_asks_too(self, two_notes, answer):
        """Esc no pasa por closeEvent: QDialog llama a reject()."""
        answer(False)
        two_notes.title_input.setText("editado")
        two_notes.show()

        two_notes.reject()

        assert two_notes.isVisible()
        two_notes._dirty = False

    def test_escape_closes_when_confirmed(self, two_notes, answer):
        answer(True)
        two_notes.title_input.setText("editado")
        two_notes.show()

        two_notes.reject()

        assert not two_notes.isVisible()

    def test_clean_dialog_closes_without_asking(self, two_notes, answer):
        boxes = answer(False)
        two_notes.note_list.setCurrentRow(0)
        two_notes.show()

        two_notes.close()

        assert boxes == []
        assert not two_notes.isVisible()


class TestDeleteConfirmation:
    """Borrar una nota es destructivo: siempre se pregunta."""

    def test_declining_does_not_delete(
        self, two_notes, mock_memory_manager, answer
    ):
        answer(False)
        two_notes.note_list.setCurrentRow(0)

        two_notes._delete_note()

        mock_memory_manager.delete_note.assert_not_called()
        assert two_notes.note_list.count() == 2
        assert two_notes.title_input.text() == "segunda"

    def test_accepting_deletes_and_clears_the_editor(
        self, two_notes, mock_memory_manager, answer
    ):
        answer(True)
        two_notes.note_list.setCurrentRow(0)

        two_notes._delete_note()

        mock_memory_manager.delete_note.assert_called_once_with(2)
        assert two_notes._current_row == -1
        assert two_notes.title_input.text() == ""
        assert two_notes.content_input.toPlainText() == ""

    def test_prompt_uses_the_delete_keys(self, two_notes, answer):
        boxes = answer(True)
        two_notes.note_list.setCurrentRow(0)

        two_notes._delete_note()

        assert len(boxes) == 1
        assert boxes[0].windowTitle() == "dialogs.notes.delete_confirm_title"
        assert boxes[0].text() == "dialogs.notes.delete_confirm_body"

    def test_dirty_note_asks_about_changes_and_then_about_deleting(
        self, two_notes, mock_memory_manager, monkeypatch
    ):
        """Primero los cambios sin guardar; aceptado eso, luego el borrado."""
        self._answer_sequence(monkeypatch, [True, False])
        two_notes.note_list.setCurrentRow(0)
        two_notes.title_input.setText("editado")

        two_notes._delete_note()

        mock_memory_manager.delete_note.assert_not_called()
        assert two_notes.title_input.text() == "editado"

    def test_dirty_note_is_deleted_when_both_prompts_are_confirmed(
        self, two_notes, mock_memory_manager, monkeypatch
    ):
        self._answer_sequence(monkeypatch, [True, True])
        two_notes.note_list.setCurrentRow(0)
        two_notes.title_input.setText("editado")

        two_notes._delete_note()

        mock_memory_manager.delete_note.assert_called_once_with(2)

    def _answer_sequence(self, monkeypatch, answers):
        """Responde a varios diálogos seguidos con ``answers`` (True = aceptar)."""
        pending = iter(answers)

        def fake_exec(self):
            return 0

        def clicked(self):
            key = (
                "dialogs.confirm.accept"
                if next(pending)
                else "dialogs.confirm.cancel"
            )
            return _button_with_text(self, key)

        monkeypatch.setattr(QMessageBox, "exec", fake_exec)
        monkeypatch.setattr(QMessageBox, "clickedButton", clicked)

    def test_without_selection_nothing_happens(
        self, two_notes, mock_memory_manager, answer
    ):
        answer(True)

        two_notes._delete_note()

        mock_memory_manager.delete_note.assert_not_called()


class TestEmptyList:
    """Sin notas la lista no es un hueco mudo."""

    def test_empty_list_shows_the_empty_label(self, dialog):
        assert dialog.empty_label.text() == "dialogs.notes.empty"
        assert dialog.empty_label.isVisibleTo(dialog) is True
        assert dialog.note_list.isVisibleTo(dialog) is False

    def test_non_empty_list_hides_the_empty_label(self, two_notes):
        assert two_notes.empty_label.isVisibleTo(two_notes) is False
        assert two_notes.note_list.isVisibleTo(two_notes) is True

    def test_saving_the_first_note_hides_the_empty_label(
        self, dialog, mock_memory_manager
    ):
        mock_memory_manager.list_notes.return_value = [
            _note(1, "primera nota", "contenido")
        ]
        dialog.title_input.setText("primera nota")
        dialog.content_input.setPlainText("contenido")

        dialog._save_note()

        assert dialog.empty_label.isVisibleTo(dialog) is False
        assert dialog.note_list.isVisibleTo(dialog) is True
