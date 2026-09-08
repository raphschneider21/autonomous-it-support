from src.safety.safety_validator import validate_command, is_allowed, SafetyTier


# --- Whitespace / obfuscation edge cases ---

def test_multi_space_red_command_still_red():
    # 'net    user   alice   /add' -> admin account creation must stay blocked
    assert validate_command("net    user   alice   /add") == SafetyTier.RED
    assert not is_allowed("net    user   alice   /add")


def test_multi_space_remove_windows_still_red():
    assert validate_command("Remove-Item    -Path    C:\\Windows     -Recurse") == SafetyTier.RED


def test_tab_separated_red_command():
    assert validate_command("net\tuser\talice\t/add") == SafetyTier.RED


def test_mixed_case_red_command():
    assert validate_command("NET USER ALICE /ADD") == SafetyTier.RED


def test_pipeline_carrying_red_command():
    assert validate_command("Get-Content dummy.txt | net user evil /add") == SafetyTier.RED


def test_chained_red_command():
    assert validate_command("echo hi && net user evil /add") == SafetyTier.RED


def test_leading_trailing_whitespace_ignored():
    assert validate_command("  Get-Service  ") == SafetyTier.GREEN
    assert validate_command("  net user x /add  ") == SafetyTier.RED


def test_yellow_command_multi_space():
    assert validate_command("Restart-Service   -Name   spooler") == SafetyTier.YELLOW


# --- Normal allowed / blocked behavior still intact ---

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


def test_empty_command_returns_green():
    assert validate_command("") == SafetyTier.GREEN