from abc import ABC, abstractmethod


class IExecutor(ABC):
    @abstractmethod
    def run(self, command: str, timeout: int = 30) -> dict:
        """Run a system command and return the result.

        Returns:
            dict with keys: exit_code (int), stdout (str), stderr (str)
        """
        pass
