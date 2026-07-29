cat >> /home/ubu/Documents/stegos-workspace/stegos/meta-stegos/recipes-security/refpolicy/files/stegos_custom.te << 'INNER'

# Allow stegd to execute dockerd and transition
gen_require(`
    type dockerd_exec_t;
')
domain_auto_trans(stegd_t, dockerd_exec_t, dockerd_t)
allow dockerd_t stegd_t:fd use;
allow dockerd_t stegd_log_t:file { append write getattr ioctl };

# Allow dockerd to manage isolated directories
allow dockerd_t container_file_t:dir { manage_dir_perms mounton };
allow dockerd_t container_file_t:file manage_file_perms;
allow dockerd_t container_file_t:lnk_file manage_lnk_file_perms;
allow dockerd_t container_file_t:sock_file manage_sock_file_perms;
allow dockerd_t container_file_t:fifo_file manage_fifo_file_perms;
INNER
