import os
import pytest
from unittest.mock import Mock, patch, mock_open
from steglib.mapper import DriveMapper

def test_mapper_init(mock_stegos_root):
    mapper = DriveMapper(root_dir=mock_stegos_root)
    assert mapper.root_dir == mock_stegos_root
    assert mapper.label_prefix == "stegos"

@patch("steglib.mapper.os.path.isfile")
def test_get_config_label_not_found(mock_isfile, mock_stegos_root):
    mock_isfile.return_value = False
    mapper = DriveMapper(root_dir=mock_stegos_root, config_file="/fake/config")
    assert mapper._get_config_label("1234") is None

@patch("steglib.mapper.os.path.isfile")
def test_get_config_label_found(mock_isfile, mock_stegos_root):
    mock_isfile.return_value = True
    mapper = DriveMapper(root_dir=mock_stegos_root, config_file="/fake/config")
    
    config_data = 'UUID="1234" TYPE="ext4" LABEL="stegos.mydata"\n'
    with patch("builtins.open", mock_open(read_data=config_data)):
        assert mapper._get_config_label("1234") == "stegos.mydata"

def test_is_mounted(mock_stegos_root):
    mapper = DriveMapper(root_dir=mock_stegos_root)
    proc_mounts = "devtmpfs /dev devtmpfs rw,nosuid,size=1024k 0 0\n" \
                  "tmpfs /stegos tmpfs rw,mode=755 0 0\n"
    
    with patch("builtins.open", mock_open(read_data=proc_mounts)):
        assert mapper._is_mounted("/stegos") is True
        assert mapper._is_mounted("/notmounted") is False

def test_setup_bind_mount(mock_subprocess, mock_stegos_root):
    mapper = DriveMapper(root_dir=mock_stegos_root)
    
    with patch.object(mapper, "_is_mounted", return_value=False):
        mapper._setup_bind_mount("/src", "group1", "repos")
    
    mock_subprocess.assert_called_once()
    args = mock_subprocess.call_args[0][0]
    assert args[0] == "mount"
    assert args[1] == "--bind"
    assert args[2] == "/src"
    assert "repos/group1" in args[3]

def test_unmount_all(mock_subprocess, mock_stegos_root):
    mapper = DriveMapper(root_dir=mock_stegos_root)
    
    proc_mounts = f"tmpfs {mock_stegos_root} tmpfs rw 0 0\n" \
                  f"/dev/sda1 {mock_stegos_root}/repos/g1 ext4 rw 0 0\n" \
                  f"tmpfs /other/dir tmpfs rw 0 0\n"
                  
    with patch("builtins.open", mock_open(read_data=proc_mounts)):
        mapper.unmount_all()
        
    assert mock_subprocess.call_count == 2

@patch("steglib.mapper.run_cmd")
@patch("steglib.mapper.os.makedirs")
@patch.object(DriveMapper, "_is_mounted", side_effect=[False, False])
@patch.object(DriveMapper, "_setup_bind_mount")
@patch("steglib.mapper.os.path.isdir")
@patch("steglib.mapper.os.listdir")
def test_mount_all_structure_a(mock_listdir, mock_isdir, mock_setup_bind, mock_is_mounted, mock_makedirs, mock_run, mock_stegos_root):
    mapper = DriveMapper(root_dir=mock_stegos_root)
    
    def run_side_effect(*args, **kwargs):
        mock_ret = Mock()
        if "blkid" in args[0]:
            mock_ret.stdout = '/dev/sda1: UUID="12345678-abcd" LABEL="stegos.sys"\n'
        return mock_ret
        
    mock_run.side_effect = run_side_effect
    mock_isdir.return_value = True # Structure A (all target folders exist)
    
    mapper.mount_all()
    
    mock_setup_bind.assert_any_call(os.path.join(mapper.base_mnt_root, "12345678-abcd", "repos"), "sys_12345678", "repos")

@patch("steglib.mapper.run_cmd")
@patch("steglib.mapper.os.makedirs")
@patch.object(DriveMapper, "_is_mounted", side_effect=[False, False])
@patch.object(DriveMapper, "_setup_bind_mount")
@patch("steglib.mapper.os.path.isdir")
@patch("steglib.mapper.os.listdir")
def test_mount_all_structure_b(mock_listdir, mock_isdir, mock_setup_bind, mock_is_mounted, mock_makedirs, mock_run, mock_stegos_root):
    mapper = DriveMapper(root_dir=mock_stegos_root)
    
    def run_side_effect(*args, **kwargs):
        mock_ret = Mock()
        if "blkid" in args[0]:
            mock_ret.stdout = '/dev/sda1: UUID="87654321-abcd" LABEL="stegos"\n'
        return mock_ret
        
    mock_run.side_effect = run_side_effect
    
    # Not structure A, but contains valid sub-groups
    def isdir_side_effect(path):
        if path.endswith("repos"):
            # if checking inside the group
            if "mygroup" in path: return True
            return False
        if path.endswith("apps") or path.endswith("persistent") or path.endswith("data") or path.endswith("config"):
            if "mygroup" in path: return True
            return False
        if "mygroup" in path: return True
        return False
        
    mock_isdir.side_effect = isdir_side_effect
    mock_listdir.return_value = ["mygroup", "notagroup"]
    
    mapper.mount_all()
    
    mock_setup_bind.assert_any_call(os.path.join(mapper.base_mnt_root, "87654321-abcd", "mygroup", "repos"), "mygroup_87654321", "repos")
