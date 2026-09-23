// Package logging emits the same JSON shape as the other Poshra services.
package logging

import (
	"log/slog"
	"os"
)

func New(level string) *slog.Logger {
	var lvl slog.Level
	if err := lvl.UnmarshalText([]byte(level)); err != nil {
		lvl = slog.LevelInfo
	}
	handler := slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: lvl})
	return slog.New(handler).With("service", "checkout")
}
