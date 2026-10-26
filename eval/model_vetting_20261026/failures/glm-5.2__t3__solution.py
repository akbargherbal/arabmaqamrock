from decimal import Decimal, ROUND_HALF_UP

COEFFS = {0.90: (105.1, 0.3059), 0.95: (111.1, 0.3126), 0.975: (122.9, 0.3081)}


def cap_report(n_letters: int, quantile: float = 0.95) -> str:
    if quantile not in COEFFS:
        raise ValueError(f"Invalid quantile: {quantile}")
    
    a, b = COEFFS[quantile]
    dur = a + b * n_letters
    
    d = Decimal(str(dur))
    dur10 = float(d.quantize(Decimal('10'), rounding=ROUND_HALF_UP))
    
    cap = int(round(dur10 * 25))
    
    return f"N={n_letters} q={quantile:.3f} dur={dur:.1f} cap={cap}"
