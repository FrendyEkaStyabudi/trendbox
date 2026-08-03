CREATE DATABASE IF NOT EXISTS trendbox
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE trendbox;

CREATE TABLE IF NOT EXISTS emotion_track (
  id INT NOT NULL AUTO_INCREMENT,
  user_id VARCHAR(255),
  emotion VARCHAR(50),
  confidence DECIMAL(8, 4),
  timestamp DATETIME,
  PRIMARY KEY (id),
  INDEX idx_emotion_timestamp (timestamp),
  INDEX idx_emotion_label (emotion)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS clothing_track (
  id INT NOT NULL AUTO_INCREMENT,
  label VARCHAR(255),
  clothing_label VARCHAR(255),
  confidence FLOAT,
  timestamp DATETIME,
  source VARCHAR(128),
  PRIMARY KEY (id),
  INDEX idx_clothing_timestamp (timestamp),
  INDEX idx_clothing_label (label)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS head_track (
  id INT NOT NULL AUTO_INCREMENT,
  label VARCHAR(255),
  confidence FLOAT,
  timestamp DATETIME,
  source VARCHAR(128),
  PRIMARY KEY (id),
  INDEX idx_head_timestamp (timestamp),
  INDEX idx_head_label (label)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS attribute_track (
  id INT NOT NULL AUTO_INCREMENT,
  clothing_label VARCHAR(255),
  confidence FLOAT,
  timestamp DATETIME,
  source VARCHAR(128),
  PRIMARY KEY (id),
  INDEX idx_attribute_timestamp (timestamp),
  INDEX idx_attribute_label (clothing_label)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
