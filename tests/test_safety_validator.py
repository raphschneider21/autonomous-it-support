from src.safety.safety_validator import validate_command, is_allowed, SafetyTier


def test_green_command_is_auto_approved():
    assert validate_command("Get-Service -Name spooler") == SafetyTier.GREEN


def test_network_diagnostics_are_green():
    assert validate_command("ipconfig /all") == SafetyTier.GREEN
    assert validate_command("Test-NetConnection -ComputerName google.com") == SafetyTier.GREEN


def test_yellow_command_requires_approval():
    assert validate_command("Restart-Service -Name spooler") == SafetyTier.YELLOW


def test_dns_flush_is_yellow():
    assert validate_command("ipconfig /flushdns") == SafetyTier.YELLOW


def test_red_command_is_blocked():
    assert validate_command("net user admin password") == SafetyTier.RED
    assert not is_allowed("net user admin password")


def test_admin_elevation_blocked():
    assert validate_command("net localgroup administrators user /add") == SafetyTier.RED


def test_system_folder_deletion_blocked():
    assert validate_command("Remove-Item -Path C:\\Windows -Recurse -Force") == SafetyTier.RED


def test_firewall_disable_blocked():
    assert validate_command("netsh advfirewall set allprofiles state off") == SafetyTier.RED