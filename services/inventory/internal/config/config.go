// Package config reads settings from the environment, and refuses to start
// without the ones that have no safe default.
package config

import (
	"fmt"
	"os"
	"strconv"
	"strings"
	"time"
)

type Config struct {
	DatabaseURL       string
	GRPCAddr          string
	HealthAddr        string
	MaxReservationTTL time.Duration
	SweepInterval     time.Duration
	LogLevel          string

	// Where to read order events from. Several addresses are only seeds: the
	// client learns the rest of the cluster from the first broker to answer.
	KafkaBrokers  []string
	OrdersTopic   string
	ConsumerGroup string
}

func Load() (Config, error) {
	dsn := os.Getenv("DATABASE_URL")
	if dsn == "" {
		// Fail at startup rather than on the first query.
		return Config{}, fmt.Errorf("DATABASE_URL is required")
	}
	// Refusing to start is the safer failure: an inventory that runs without
	// its consumer keeps holding stock that was already sold, and nothing
	// looks wrong until the holds start expiring.
	brokers := splitList(os.Getenv("KAFKA_BROKERS"))
	if len(brokers) == 0 {
		return Config{}, fmt.Errorf("KAFKA_BROKERS is required")
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
		KafkaBrokers:      brokers,
		OrdersTopic:       envOr("ORDERS_TOPIC", "poshra.orders.created.v1"),
		// The group name is the identity of this reader. Change it and Kafka
		// treats it as a brand new consumer that has seen nothing.
		ConsumerGroup: envOr("CONSUMER_GROUP", "inventory-order-settler"),
	}, nil
}

// splitList reads a comma-separated environment value, ignoring spacing.
func splitList(value string) []string {
	var out []string
	for _, part := range strings.Split(value, ",") {
		if part = strings.TrimSpace(part); part != "" {
			out = append(out, part)
		}
	}
	return out
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
