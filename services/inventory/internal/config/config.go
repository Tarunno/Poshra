// Package config reads settings from the environment, and refuses to start
// without the ones that have no safe default.
package config

import (
	"fmt"
	"os"
	"strconv"
	"time"
)

type Config struct {
	DatabaseURL       string
	GRPCAddr          string
	HealthAddr        string
	MaxReservationTTL time.Duration
	SweepInterval     time.Duration
	LogLevel          string
}

func Load() (Config, error) {
	dsn := os.Getenv("DATABASE_URL")
	if dsn == "" {
		// Fail at startup rather than on the first query.
		return Config{}, fmt.Errorf("DATABASE_URL is required")
	}
	return Config{
		DatabaseURL: dsn,
		GRPCAddr:    envOr("GRPC_ADDR", ":50051"),
		HealthAddr:  envOr("HEALTH_ADDR", ":8081"),
		// A client asking for a longer hold gets this instead: stock must not
		// be reservable indefinitely by a buggy or hostile caller.
		MaxReservationTTL: envDuration("MAX_RESERVATION_TTL", 30*time.Minute),
		SweepInterval:     envDuration("SWEEP_INTERVAL", time.Minute),
		LogLevel:          envOr("LOG_LEVEL", "info"),
	}, nil
}

func envOr(key, fallback string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return fallback
}

func envDuration(key string, fallback time.Duration) time.Duration {
	raw := os.Getenv(key)
	if raw == "" {
		return fallback
	}
	if seconds, err := strconv.Atoi(raw); err == nil {
		return time.Duration(seconds) * time.Second
	}
	if d, err := time.ParseDuration(raw); err == nil {
		return d
	}
	return fallback
}
