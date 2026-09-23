// Package server maps the gRPC contract onto the store.
//
// The handlers stay thin on purpose: validate the request, call one store
// method, translate the error. The rules that must hold under concurrency live
// in the store, inside a transaction.
package server

import (
	"context"
	"errors"
	"time"

	"github.com/google/uuid"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/types/known/timestamppb"

	inventoryv1 "github.com/Tarunno/Poshra/services/inventory/gen/poshra/inventory/v1"
	"github.com/Tarunno/Poshra/services/inventory/internal/store"
)

const defaultTTL = 15 * time.Minute

type Server struct {
	// Embedding the generated type means adding an RPC to the contract does
	// not break compilation here; it returns Unimplemented until written.
	inventoryv1.UnimplementedInventoryServiceServer

	store     *store.Store
	maxTTL    time.Duration
	defaultTL time.Duration
}

func New(s *store.Store, maxTTL time.Duration) *Server {
	return &Server{store: s, maxTTL: maxTTL, defaultTL: defaultTTL}
}

func (s *Server) ReserveStock(
	ctx context.Context,
	req *inventoryv1.ReserveStockRequest,
) (*inventoryv1.ReserveStockResponse, error) {
	if err := validUUID(req.GetReservationId(), "reservation_id"); err != nil {
		return nil, err
	}
	if err := validUUID(req.GetOrderId(), "order_id"); err != nil {
		return nil, err
	}
	if len(req.GetItems()) == 0 {
		return nil, status.Error(codes.InvalidArgument, "items must not be empty")
	}

	items := make([]store.Item, 0, len(req.GetItems()))
	for _, item := range req.GetItems() {
		if err := validUUID(item.GetSkuId(), "sku_id"); err != nil {
			return nil, err
		}
		if item.GetQuantity() <= 0 {
			return nil, status.Error(codes.InvalidArgument, "quantity must be positive")
		}
		items = append(items, store.Item{SKUID: item.GetSkuId(), Quantity: item.GetQuantity()})
	}

	ttl := s.defaultTL
	if seconds := req.GetTtlSeconds(); seconds > 0 {
		ttl = time.Duration(seconds) * time.Second
	}
	if ttl > s.maxTTL {
		// Clamp rather than reject: the caller still gets a hold, just not an
		// indefinite one.
		ttl = s.maxTTL
	}

	reservation, created, err := s.store.Reserve(
		ctx, req.GetReservationId(), req.GetOrderId(), items, ttl)
	if err != nil {
		return nil, translate(err)
	}

	return &inventoryv1.ReserveStockResponse{
		ReservationId: reservation.ID,
		State:         toProtoState(reservation.State),
		ExpiresAt:     timestamppb.New(reservation.ExpiresAt),
		Created:       created,
	}, nil
}

func (s *Server) CommitReservation(
	ctx context.Context,
	req *inventoryv1.CommitReservationRequest,
) (*inventoryv1.CommitReservationResponse, error) {
	if err := validUUID(req.GetReservationId(), "reservation_id"); err != nil {
		return nil, err
	}
	state, err := s.store.Commit(ctx, req.GetReservationId())
	if err != nil {
		return nil, translate(err)
	}
	return &inventoryv1.CommitReservationResponse{State: toProtoState(state)}, nil
}

func (s *Server) ReleaseReservation(
	ctx context.Context,
	req *inventoryv1.ReleaseReservationRequest,
) (*inventoryv1.ReleaseReservationResponse, error) {
	if err := validUUID(req.GetReservationId(), "reservation_id"); err != nil {
		return nil, err
	}
	state, err := s.store.Release(ctx, req.GetReservationId(), req.GetReason(), false)
	if err != nil {
		return nil, translate(err)
	}
	return &inventoryv1.ReleaseReservationResponse{State: toProtoState(state)}, nil
}

func (s *Server) GetStock(
	ctx context.Context,
	req *inventoryv1.GetStockRequest,
) (*inventoryv1.GetStockResponse, error) {
	if len(req.GetSkuIds()) == 0 {
		return nil, status.Error(codes.InvalidArgument, "sku_ids must not be empty")
	}
	levels, err := s.store.Levels(ctx, req.GetSkuIds())
	if err != nil {
		return nil, translate(err)
	}

	out := make([]*inventoryv1.StockLevel, 0, len(levels))
	for _, level := range levels {
		out = append(out, &inventoryv1.StockLevel{
			SkuId:     level.SKUID,
			Available: level.Available,
			Reserved:  level.Reserved,
		})
	}
	return &inventoryv1.GetStockResponse{Levels: out}, nil
}

func (s *Server) SetStock(
	ctx context.Context,
	req *inventoryv1.SetStockRequest,
) (*inventoryv1.SetStockResponse, error) {
	if err := validUUID(req.GetSkuId(), "sku_id"); err != nil {
		return nil, err
	}
	if req.GetQuantity() < 0 {
		return nil, status.Error(codes.InvalidArgument, "quantity must not be negative")
	}
	level, err := s.store.SetStock(ctx, req.GetSkuId(), req.GetQuantity())
	if err != nil {
		return nil, translate(err)
	}
	return &inventoryv1.SetStockResponse{Level: &inventoryv1.StockLevel{
		SkuId:     level.SKUID,
		Available: level.Available,
		Reserved:  level.Reserved,
	}}, nil
}

func validUUID(value, field string) error {
	if value == "" {
		return status.Errorf(codes.InvalidArgument, "%s is required", field)
	}
	if _, err := uuid.Parse(value); err != nil {
		return status.Errorf(codes.InvalidArgument, "%s must be a uuid", field)
	}
	return nil
}

// translate maps store errors onto gRPC status codes.
//
// The code is part of the contract: a caller decides whether to retry from it.
// FailedPrecondition says "your request is fine, the state is not" and must
// not be retried blindly; Unavailable may be.
func translate(err error) error {
	switch {
	case errors.Is(err, store.ErrNotFound):
		return status.Error(codes.NotFound, "reservation not found")
	case errors.Is(err, store.ErrUnknownSKU):
		return status.Error(codes.NotFound, err.Error())
	case errors.Is(err, store.ErrInsufficient):
		// Retrying will not create stock, so this is not Unavailable.
		return status.Error(codes.FailedPrecondition, err.Error())
	case errors.Is(err, store.ErrAlreadySettled):
		return status.Error(codes.FailedPrecondition, err.Error())
	case errors.Is(err, context.DeadlineExceeded):
		return status.Error(codes.DeadlineExceeded, "inventory timed out")
	default:
		// Never hand a database error to a caller: it leaks schema details.
		return status.Error(codes.Internal, "internal error")
	}
}

func toProtoState(state store.State) inventoryv1.ReservationState {
	switch state {
	case store.StateHeld:
		return inventoryv1.ReservationState_RESERVATION_STATE_HELD
	case store.StateCommitted:
		return inventoryv1.ReservationState_RESERVATION_STATE_COMMITTED
	case store.StateReleased:
		return inventoryv1.ReservationState_RESERVATION_STATE_RELEASED
	case store.StateExpired:
		return inventoryv1.ReservationState_RESERVATION_STATE_EXPIRED
	default:
		return inventoryv1.ReservationState_RESERVATION_STATE_UNSPECIFIED
	}
}
