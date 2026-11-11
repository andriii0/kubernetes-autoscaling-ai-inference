This was the first HPA run in the main v1.1 series. It reused the rate of 8 requests per 10 seconds selected by the original pilot. HPA grew from one to two copies, all 241 requests succeeded, and primary p95 was 1.445 seconds.

Later fixed-one runs also met the same target at rate 8. The pilot measurements were valid, but this rate did not reproduce stable overload under the main-series conditions. This run shows that HPA worked; it does not show that HPA was needed or better than fixed capacity.
