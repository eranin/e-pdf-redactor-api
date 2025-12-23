class StorageDriver:
    def download(self, uri: str) -> bytes:
        raise NotImplementedError

    def upload(self, uri: str, content: bytes) -> str:
        raise NotImplementedError
