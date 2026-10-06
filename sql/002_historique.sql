CREATE TABLE IF NOT EXISTS historique_etats (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    identifiant VARCHAR(2) NOT NULL,
    etat ENUM('disponible', 'occupe') NOT NULL,
    session_id CHAR(36) NOT NULL,
    numero BIGINT UNSIGNED NOT NULL,
    recu_le DATETIME(6) NOT NULL,
    UNIQUE KEY une_mise_a_jour (session_id, identifiant, numero),
    INDEX par_vehicule (identifiant, recu_le)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
