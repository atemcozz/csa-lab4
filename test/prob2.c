
void print_abs(int n) {
    int d = n / 10;
    if (d > 0) {
        print_abs(d);
    }
    out((n - d * 10) + '0', 0);
}

void print_num(int n) {
    if (n < 0) {
        out('-', 0);
        n = -n;
    }
    print_abs(n);
}


int main() {
    int n = 100;

    int sum = 0;
    int sum_sq = 0;
    int result = 0;

    // sum = n(n+1)/2
    sum = n * (n + 1) / 2;

    // sum_sq = n(n+1)(2n+1)/6
    sum_sq = n * (n + 1) * (2 * n + 1) / 6;

    result = sum * sum - sum_sq;

    print_num(result);

    return 0;
}