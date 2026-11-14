// Package monotonic exposes elapsed Go monotonic time to the benchmark script.
package monotonic

import (
	"go.k6.io/k6/v2/js/modules"
	"time"
)

var epoch = time.Now()

func init() { modules.Register("k6/x/monotonic", new(Root)) }

type Root struct{}
type Instance struct{}

func (*Root) NewModuleInstance(modules.VU) modules.Instance { return new(Instance) }

func (*Instance) Exports() modules.Exports {
	return modules.Exports{Default: map[string]interface{}{
		"now": func() float64 { return float64(time.Since(epoch)) / float64(time.Millisecond) },
	}}
}
