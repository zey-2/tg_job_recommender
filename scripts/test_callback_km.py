import asyncio
from types import SimpleNamespace
from bot import JobBot


class DummyQuery:
    def __init__(self, data, message_text='Original'):
        self.data = data
        self.message = SimpleNamespace(text=message_text)

    async def answer(self):
        print('Answered CallbackQuery')

    async def edit_message_text(self, text, reply_markup=None, parse_mode=None):
        print('edit_message_text called with:', text)


class DummyUpdate:
    def __init__(self, user_id, data):
        self.callback_query = DummyQuery(data)
        self._effective_user = SimpleNamespace(id=user_id)

    @property
    def effective_user(self):
        return self._effective_user


async def test():
    bot = JobBot()

    # Simulate view_keywords inline keyboard button click: 'km:menu'
    print('\n--- Simulating km:menu ---')
    u = DummyUpdate(1234, 'km:menu')
    await bot.button_callback(u, None)

    # Simulate remove_one with no keywords yet
    print('\n--- Simulating km:remove_one ---')
    u2 = DummyUpdate(1234, 'km:remove_one')
    await bot.button_callback(u2, None)

    # Simulate confirm clear auto
    print('\n--- Simulating km:clear_auto_confirm ---')
    u3 = DummyUpdate(1234, 'km:clear_auto_confirm')
    await bot.button_callback(u3, None)

    # Simulate unknown command
    print('\n--- Simulating km:unknown ---')
    u4 = DummyUpdate(1234, 'km:unknown')
    await bot.button_callback(u4, None)


if __name__ == '__main__':
    asyncio.run(test())
