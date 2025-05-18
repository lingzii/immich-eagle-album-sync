import anyio

send_channel, receive_channel = anyio.create_memory_object_stream(100)
