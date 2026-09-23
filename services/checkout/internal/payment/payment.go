// Package payment is the boundary where money would change hands.
//
// It is an interface with a fake behind it, so the order flow can be built and
// tested now and a real processor dropped in later without touching checkout.
package payment

import (
	"context"
	"errors"
	"fmt"

	"github.com/google/uuid"
)

var ErrDeclined = errors.New("payment declined")

type Charge struct {
	OrderID    string
	AmountRate int64 // minor units
	Currency   string
	Token      string // from the client; a real processor would exchange this
}

type Receipt struct {
	Reference string
}

type Processor interface {
	Charge(ctx context.Context, charge Charge) (Receipt, error)
}

// Fake approves everything except a token that asks to be declined, which is
// how the failure path gets exercised end to end.
type Fake struct{}

const DeclineToken = "decline"

func (Fake) Charge(_ context.Context, charge Charge) (Receipt, error) {
	if charge.Token == DeclineToken {
		return Receipt{}, fmt.Errorf("%w: test token", ErrDeclined)
	}
	if charge.AmountRate <= 0 {
		return Receipt{}, fmt.Errorf("%w: nothing to charge", ErrDeclined)
	}
	return Receipt{Reference: "fake_" + uuid.NewString()}, nil
}
