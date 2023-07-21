import traceback

import streamlit as st
import asyncio
from codeinterpreterapi import CodeInterpreterSession
from codeinterpreterapi import File
import sqlite3
from datetime import datetime


# Function to create a database connection and initialize tables
def initialize_database():
    conn = sqlite3.connect('chat.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL DEFAULT 'New Chat',
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            category TEXT,
            content TEXT,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            FOREIGN KEY(chat_id) REFERENCES chats(id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS generated_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_message_id INTEGER,
            name TEXT,
            content BLOB,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            FOREIGN KEY(chat_message_id) REFERENCES chat_messages(id)
        )
    ''')
    return conn, cursor


# Function to save chat to database
def save_chat_to_database(conn, cursor, title):
    now = datetime.now()
    cursor.execute('''
        INSERT INTO chats (title, created_at, updated_at)
        VALUES (?, ?, ?)
    ''', (title, now, now))
    conn.commit()
    return cursor.lastrowid


# Function to update chat title in database
def update_chat_title(conn, cursor, chat_id, title):
    now = datetime.now()
    cursor.execute('''
        UPDATE chats
        SET title = ?, updated_at = ?
        WHERE id = ?
    ''', (title, now, chat_id))
    conn.commit()


# Function to save chat message to database
def save_message_to_database(conn, cursor, chat_id, category, content):
    now = datetime.now()
    cursor.execute('''
        INSERT INTO chat_messages (chat_id, category, content, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (chat_id, category, content, now, now))
    conn.commit()
    return cursor.lastrowid


# Function to save generated file to database
def save_file_to_database(conn, cursor, chat_message_id, name, content):
    now = datetime.now()
    cursor.execute('''
        INSERT INTO generated_files (chat_message_id, name, content, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (chat_message_id, name, content, now, now))
    conn.commit()


# Function to get all chats from the database
def get_chats_from_database(cursor):
    cursor.execute("SELECT * FROM chats ORDER BY updated_at DESC")
    return cursor.fetchall()


def get_chat_from_database(cursor, chat_id):
    cursor.execute("SELECT * FROM chats WHERE id = ?", (chat_id,))
    return cursor.fetchone()


# Function to get chat messages by chat_id
def get_chat_messages_from_database(cursor, chat_id):
    cursor.execute("SELECT * FROM chat_messages WHERE chat_id = ?", (chat_id,))
    return cursor.fetchall()


def get_chat_message_from_database(cursor, chat_message_id):
    cursor.execute("SELECT * FROM chat_messages WHERE id = ?", (chat_message_id,))
    return cursor.fetchone()


def get_generated_files_from_database(cursor, chat_message_id):
    cursor.execute("SELECT * FROM generated_files WHERE chat_message_id = ?", (chat_message_id,))
    return cursor.fetchall()


def reload_from_chat_id(cursor, chat_id):
    st.session_state.chats = get_chats_from_database(cursor)
    st.session_state.current_chat = get_chat_from_database(cursor, chat_id)
    st.session_state.chat_messages = get_chat_messages_from_database(cursor, chat_id)


async def process(prompt, uploaded_files):
    files = []
    print(uploaded_files)
    for uploaded_file in uploaded_files:
        file = File(
            name=uploaded_file.name,
            content=uploaded_file.read()
        )
        files.append(file)
    async with CodeInterpreterSession(model='gpt-4') as session:
        response = await session.generate_response(
            prompt,
            files=files,
            detailed_error=True
        )
        return response


# Initialize database
conn, cursor = initialize_database()

# Initialize session states
if 'current_chat' not in st.session_state:
    st.session_state.current_chat = None

if 'chats' not in st.session_state:
    st.session_state.chats = get_chats_from_database(cursor)

if 'chat_messages' not in st.session_state:
    st.session_state.chat_messages = []

# Streamlit UI layout
with st.sidebar:
    # st.title("Code Interpreter Chat")
    if st.button("New Chat", key="new_chat"):
        # 現在の日付と時刻をタイトルにする
        chat_title = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
        chat_id = save_chat_to_database(conn, cursor, chat_title)
        st.session_state.current_chat = get_chat_from_database(cursor, chat_id)
        st.session_state.chats = get_chats_from_database(cursor)
    # openai_api_key = st.text_input("OpenAI API Key", key="chatbot_api_key", type="password")
    st.session_state.current_chat = st.radio("Chat Histories", st.session_state.chats, format_func=lambda x: x[1])

if st.session_state.current_chat is None:
    st.caption("Please select a chat history or press 'New Chat' from the sidebar")

header_container = st.container()
chat_container = st.container()
form_container = st.container()

if st.session_state.current_chat is not None:
    chat_id = st.session_state.current_chat[0]
    chat_title = st.session_state.current_chat[1]
    st.session_state.chat_messages = get_chat_messages_from_database(cursor, chat_id)

    with header_container:
        new_chat_title = st.text_input("Chat Title", value=chat_title)
        if st.button("Save Title"):
            update_chat_title(conn, cursor, chat_id, new_chat_title)
            reload_from_chat_id(cursor, chat_id)

    with chat_container:
        for chat_message in st.session_state.chat_messages:
            chat_message_id = chat_message[0]
            category = chat_message[2]
            content = chat_message[3]
            if category == 'user':
                with st.chat_message("user"):
                    st.write(content)
            else:
                with st.chat_message("assistant"):
                    st.write(content)
                    # Display file download buttons
                    files = get_generated_files_from_database(cursor, chat_message_id)
                    for file in files:
                        data = file[3]
                        file_name = file[2]
                        st.download_button(
                            label=f"Download: {file_name}",
                            data=data,
                            file_name=file_name,
                        )

    with st.form(key="user_input", clear_on_submit=True):
        uploaded_files = st.file_uploader(
            "Choose files for analysis:",
            accept_multiple_files=True
        )
        text_area = st.text_area(
            "Enter your message:",
            placeholder="Enter your message",
            value=""
        )
        if st.form_submit_button("Submit"):
            user_message = text_area
            # Display the user prompt
            message_id = save_message_to_database(conn, cursor, chat_id, "user", user_message)
            user_chat_message = get_chat_message_from_database(cursor, message_id)
            st.session_state.chat_messages.append(user_chat_message)
            with chat_container:
                st.chat_message("user").write(user_message)

            # Create a new session
            print(f"User message: {user_message}")

            try:
                # Generate response
                response = asyncio.run(process(user_message, uploaded_files))

                # Save to database
                message_id = save_message_to_database(conn, cursor, chat_id, "assistant", response.content)
                assistant_chat_message = get_chat_message_from_database(cursor, message_id)
                st.session_state.chat_messages.append(assistant_chat_message)

                with chat_container:
                    st.chat_message("assistant").write(response.content)
                    for file in response.files:
                        data = file.content
                        file_name = file.name
                        save_file_to_database(conn, cursor, message_id, file_name, data)
                        st.download_button(
                            label=f"Download: {file_name}",
                            data=data,
                            file_name=file_name,
                        )

            except Exception as e:
                with chat_container:
                    st.write(f"An error occurred: {e.__class__.__name__}: {e}")
                    st.write(traceback.format_exc())
