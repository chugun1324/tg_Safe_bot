from aiogram.fsm.state import State, StatesGroup


class RegistrationState(StatesGroup):
    waiting_nickname = State()
    waiting_contact = State()
    waiting_role = State()


class CreateOrderState(StatesGroup):
    waiting_artist_username = State()
    waiting_title = State()
    waiting_price = State()


class ReportState(StatesGroup):
    waiting_target_tg_id = State()
    waiting_order_id = State()
    waiting_reason = State()


class SearchState(StatesGroup):
    waiting_query = State()


class SendArtState(StatesGroup):
    waiting_order_id = State()
    waiting_kind = State()
    waiting_media = State()


class RelayState(StatesGroup):
    waiting_order_id = State()
    waiting_message = State()


class NDAState(StatesGroup):
    waiting_order_id = State()


class AdminState(StatesGroup):
    waiting_blocks_query = State()
    waiting_users_query = State()
