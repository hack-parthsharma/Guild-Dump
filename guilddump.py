import asyncio
import csv
import pathlib
import time

import discord
from simple_term_menu import TerminalMenu


async def input_prompt(question: str, default: str = '', checker=None) -> str:
    while True:
        try:
            result = input(question) or default
        except KeyboardInterrupt:
            exit(1)

        if checker is None:
            return result
        elif asyncio.iscoroutinefunction(checker) and await checker(result):
            return result
        elif not asyncio.iscoroutinefunction(checker) and checker(result):
            return result

        print('\r')


async def option_prompt(question: str, options: [str]) -> int:
    print(question)
    return TerminalMenu(options, clear_menu_on_exit=False).show()


async def select_prompt(question: str, options: [str]) -> [int]:
    print(question)
    return TerminalMenu(options, clear_menu_on_exit=False, multi_select=True, preselected_entries=options).show()


async def yesno_prompt(question: str) -> bool:
    return option_prompt(question, ['Yes', 'No']) == 0


async def request_client() -> discord.Client:
    intents = discord.Intents().default()
    intents.members = True

    async def checker(checker_token: str) -> bool:
        checker_client = discord.Client(intents=intents)
        try:
            await checker_client.login(checker_token)
            await checker_client.close()
            return True
        except discord.LoginFailure:
            print('Invalid token')
            await checker_client.close()
            return False

    token = await input_prompt('Discord Bot Token: ', checker=checker)

    client = discord.Client(intents=intents)
    await client.login(token)
    return client


async def request_guild(client: discord.Client) -> discord.Guild:
    options = []
    guilds = [guild async for guild in client.fetch_guilds(limit=51)]

    if len(guilds) > 50:
        manual = True
    elif len(guilds) <= 10:
        manual = False
    else:
        option = await option_prompt(f'{len(guilds)} guilds are available. Choose from list or enter manually?: ', ['Choose', 'Manually'])
        manual = option == 1

    if manual:
        async def checker(guild_id: str) -> bool:
            try:
                return await client.fetch_guild(int(guild_id)) is not None
            except ValueError:
                print('Enter a valid id (must only contain number)')
            except discord.Forbidden:
                print('Bot not in guild')

            return False

        return await client.fetch_guild(int(await input_prompt('Guild id to scrape: ', checker=checker)))
    else:
        for guild in guilds:
            options.append(f'{guild.id} ({guild.name})')

        return guilds[await option_prompt('Select guild to scrape: ', options)]


async def request_directory() -> pathlib.Path:
    async def checker(directory: str) -> bool:
        path = pathlib.Path(directory)
        if path.exists():
            if path.is_dir():
                return True
            else:
                print(f'{directory} is not a directory')
        else:
            if await yesno_prompt(f'{directory} does not exist. Do you want to create it?'):
                try:
                    path.mkdir(parents=True)
                    return True
                except OSError as e:
                    print(f'Failed to create directory: {e}')

        return False

    return pathlib.Path(await input_prompt('Directory to save content in: ', checker=checker))


async def request_channels(guild: discord.Guild) -> [discord.TextChannel]:
    options = list(filter(lambda channel: isinstance(channel, discord.TextChannel), await guild.fetch_channels()))
    selected = await select_prompt('Select channels to scrape: ', [f'{channel.id} (#{channel.name})' for channel in options])
    return [options[select] for select in selected]


async def request_max_members() -> int:
    def checker(number: str) -> bool:
        try:
            if int(number) > 0:
                return True
            else:
                print('Value must be greater than 0')
                return False
        except ValueError:
            return False

    return int(await input_prompt(f'Max members to fetch (default: 1000): ', default='1000', checker=checker))


async def request_max_messages() -> int:
    def checker(number: str) -> bool:
        try:
            if int(number) > 0:
                return True
            else:
                print('Value must be greater than 0')
                return False
        except ValueError:
            return False

    return int(await input_prompt(f'Max messages to fetch per channel (default: 1000): ', default='1000', checker=checker))


async def dump_channels(guild: discord.Guild, channel_writer):
    channel_writer.writerow(['id', 'created_at', 'name', 'type'])

    for channel in await guild.fetch_channels():
        channel_type = ''
        if isinstance(channel, discord.TextChannel):
            channel_type = 'text'
        elif isinstance(channel, discord.VoiceChannel):
            channel_type = 'voice'
        elif isinstance(channel, discord.CategoryChannel):
            channel_type = 'category'
        elif isinstance(channel, discord.StageChannel):
            channel_type = 'stage'

        channel_writer.writerow([
            channel.id,
            int(time.mktime(channel.created_at.timetuple())),
            channel.name,
            channel_type
        ])


async def dump_members(guild: discord.Guild, limit: int, user_writer):
    user_writer.writerow(['id', 'joined_at', 'name', 'nick', 'is_bot', 'premium_since'])

    async for member in guild.fetch_members(limit=limit):
        user_writer.writerow([
            member.id,
            int(time.mktime(member.joined_at.timetuple())),
            str(member),
            member.nick,
            member.bot,
            int(time.mktime(member.premium_since.timetuple())) if member.premium_since else 0
        ])


async def dump_roles(guild: discord.Guild, role_writer):
    role_writer.writerow(['id', 'created_at', 'name', 'position', 'permissions', 'member_count', 'is_mentionable', 'color'])

    for role in await guild.fetch_roles():
        role_writer.writerow([
            role.id,
            role.created_at,
            role.name,
            role.position,
            role.permissions.value,
            len(role.members),
            role.mentionable,
            role.color
        ])


async def dump_messages(channel: discord.TextChannel, limit: int, message_writer, attachment_writer, reaction_writer, embed_writer):
    message_writer.writerow(['id', 'author_id', 'created_at', 'modified_at', 'content'])
    attachment_writer.writerow(['message_id', 'type', 'size', 'filename', 'url', 'is_spoiler'])
    reaction_writer.writerow(['message_id', 'name', 'reaction_count', 'is_animated'])
    embed_writer.writerow(['message_id', 'title', 'description', 'footer', 'image', 'thumbnail', 'video', 'author', 'field_count', 'color'])

    async for message in channel.history(limit=limit):
        message_writer.writerow([
            message.id,
            message.author.id,
            int(time.mktime(message.created_at.timetuple())),
            int(time.mktime(message.edited_at.timetuple())) if message.edited_at else 0,
            message.content
        ])
        if message.attachments:
            for attachment in message.attachments:
                attachment_writer.writerow([
                    message.id,
                    attachment.content_type,
                    attachment.size,
                    attachment.filename,
                    attachment.url,
                    attachment.is_spoiler()
                ])
        if message.reactions:
            for reaction in message.reactions:
                reaction_writer.writerow([
                    message.id,
                    reaction.emoji if isinstance(reaction.emoji, str) else reaction.emoji.name,
                    reaction.count,
                    False if isinstance(reaction.emoji, str) else reaction.emoji.animated
                ])
        if message.embeds:
            for embed in message.embeds:
                embed_writer.writerow([
                    message.id,
                    embed.title if embed.title else None,
                    embed.description if embed.description else None,
                    embed.footer.text if embed.footer else None,
                    embed.image.url if embed.image else None,
                    embed.thumbnail.url if embed.thumbnail else None,
                    embed.video.url if embed.video else None,
                    embed.author.name if embed.author else None,
                    len(embed.fields),
                    embed.color if embed.color else None
                ])


async def main():
    client = await request_client()

    try:
        guild = await request_guild(client)
        directory = (await request_directory()).joinpath(str(guild.id))
        if directory.exists():
            print(f'Directory for guild already exists ({directory.absolute()})')
            return
        else:
            directory.mkdir()

        max_members = await request_max_members()
        max_messages = await request_max_messages()

        selected_channels = await request_channels(guild)

        print('Starting dumping, this make take a while...')

        with directory.joinpath('channels.csv').open('w+') as channels:
            await dump_channels(guild, csv.writer(channels))
            print('Dumped channels')

        with directory.joinpath('members.csv').open('w+') as members:
            await dump_members(guild, max_members, csv.writer(members))
            print('Dumped members')

        with directory.joinpath('roles.csv').open('w+') as roles:
            await dump_roles(guild, csv.writer(roles))
            print('Dumped roles')

        for channel in selected_channels:
            if isinstance(channel, discord.TextChannel):
                dir = directory.joinpath(str(channel.id))
                dir.mkdir()
                with dir.joinpath('messages.csv').open('w+') as messages, dir.joinpath('attachments.csv').open('w+') as attachments, dir.joinpath('reactions.csv').open('w+') as reactions, dir.joinpath('embeds.csv').open('w+') as embeds:
                    await dump_messages(channel, max_messages, csv.writer(messages), csv.writer(attachments), csv.writer(reactions), csv.writer(embeds))
                    print(f'Dumped channel {channel.id} (#{channel.name})')

        print('Finished dumping')
    finally:
        await client.close()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except RuntimeError:
        pass
