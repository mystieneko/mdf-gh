DROP TABLE IF EXISTS posts;
DROP TABLE IF EXISTS pages;
DROP TABLE IF EXISTS users;

CREATE TABLE pages (
	id INT PRIMARY KEY AUTO_INCREMENT,
	title TEXT NOT NULL,
	slug TEXT NOT NULL,
	content TEXT NOT NULL
) ENGINE=InnoDB;

CREATE TABLE posts (
	id INT PRIMARY KEY AUTO_INCREMENT,
	created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
	title TEXT NOT NULL,
	slug TEXT NOT NULL,
	content TEXT NOT NULL,
	tags TEXT NOT NULL,
	authors TEXT NOT NULL,
	categories TEXT NOT NULL
) ENGINE=InnoDB;

CREATE TABLE users (
	id INT PRIMARY KEY AUTO_INCREMENT,
	name VARCHAR(50),
	email VARCHAR(100),
	password VARCHAR(255),
	is_approved BOOLEAN,
	role VARCHAR(50),
	avatar_url VARCHAR(255) DEFAULT "/static/avatars/default.svg",
	bio TEXT
) ENGINE=InnoDB;

INSERT INTO `users` (`id`, `name`, `email`, `password`, `is_approved`, `role`, `avatar_url`, `bio`) VALUES
(1, 'admin', 'admin@example.com', '$2b$12$vCPKvlKpvDZ7EEyJb0VhGOJvP5WKNrp9zwAZ5Efp0eZHquVkawwDO', 1, 'administrator', '/static/avatars/default.svg', NULL);