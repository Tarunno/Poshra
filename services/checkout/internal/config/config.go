// Package config reads settings from the environment and refuses to start
// without the ones that have no safe default.
package config

import (
	"fmt"
	"os"
	"time"
)

type Config struct {
	DatabaseURL  string
	HTTPAddr     string
	InventoryURL string
	CatalogURL   string
	LogLevel     string

	// One budget per outbound hop, so a slow dependency cannot consume the
	// whole request and leave the caller waiting.
	InventoryTimeout time.Duration
	CatalogTimeout   time.Duration
	PaymentTimeout   time.Duration
	ReservationTTL   time.Duration
}

func Load() (Config, error) {
	dsn := os.Getenv("DATABASE_URL")
	if dsn == "" {
		return Config{}, fmt.Errorf("DATABASE_URL is required")
	}
	inventory := os.Getenv("INVENTORY_ADDR")
	if inventory == "" {
		return Config{}, fmt.Errorf("INVENTORY_ADDR is required")
	}
	catalog := os.Getenv("CATALOG_URL")
	if catalog == "" {
		return Config{}, fmt.Errorf("CATALOG_URL is required")
	}

	return Config{
		DatabaseURL:      dsn,
		HTTPAddr:         envOr("HTTP_ADDR", ":8080"),
		InventoryURL:     inventory,
		CatalogURL:       catalog,
		LogLevel:         envOr("LOG_LEVEL", "info"),
		InventoryTimeout: 800 * time.Millisecond,
		CatalogTimeout:   2 * time.Second,
		PaymentTimeout:   5 * time.Second,
		// Long enough to survive a slow payment, short enough that abandoned
		// checkouts return stock quickly.
		ReservationTTL: 15 * time.Minute,
	}, nil
}

func envOr(key, fallback string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return fallback
}
