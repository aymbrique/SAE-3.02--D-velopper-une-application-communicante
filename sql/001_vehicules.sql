CREATE TABLE IF NOT EXISTS vehicules (
    identifiant VARCHAR(2) PRIMARY KEY,
    etat ENUM('disponible', 'occupe') NOT NULL,
    session_id CHAR(36) NOT NULL,
    numero BIGINT UNSIGNED NOT NULL,
    recu_le DATETIME(6) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
