

int a[2];
int b[2];
int res[2];

void add_64(int n1[], int n2[], int r[]) {
    int a_lo_lo = n1[1] & 65535;
    int a_lo_hi = (n1[1] >> 16) & 65535;
    
    int b_lo_lo = n2[1] & 65535;
    int b_lo_hi = (n2[1] >> 16) & 65535;
    
    int lo_lo = a_lo_lo + b_lo_lo;
    int carry = (lo_lo >> 16) & 1;
    
    int lo_hi = a_lo_hi + b_lo_hi + carry;
    carry = (lo_hi >> 16) & 1;
    
    r[1] = ((lo_hi & 65535) << 16) | (lo_lo & 65535);
    r[0] = n1[0] + n2[0] + carry;
}

int ret_hi = 0;
int ret_lo = 0;
int ret_rem = 0;

void div_10_64_val(int hi, int lo) {
    int h_hi = (hi >> 16) & 65535;
    int h_lo = hi & 65535;
    int l_hi = (lo >> 16) & 65535;
    int l_lo = lo & 65535;

    int r = 0;
    
    int t = r * 65536 + h_hi;
    int q3 = t / 10;
    r = t % 10;
    
    t = r * 65536 + h_lo;
    int q2 = t / 10;
    r = t % 10;
    
    t = r * 65536 + l_hi;
    int q1 = t / 10;
    r = t % 10;
    
    t = r * 65536 + l_lo;
    int q0 = t / 10;
    r = t % 10;

    ret_hi = (q3 << 16) | (q2 & 65535);
    ret_lo = (q1 << 16) | (q0 & 65535);
    ret_rem = r;
}


void print_abs_val(int hi, int lo) {
    if (hi == 0 && lo == 0) {
        return;
    }
    
    int str[25];
    int i = 1;
    
    while (hi != 0 || lo != 0) {
        div_10_64_val(hi, lo);
        str[i] = ret_rem;
        i = i + 1;
        hi = ret_hi;
        lo = ret_lo;
    }
    
    while (i > 1) {
        i = i - 1;
        out(str[i] + '0', 0);
    }
}

void neg_64(int n[], int r[]) {
    int a_lo_lo = (~n[1]) & 65535;
    int a_lo_hi = ((~n[1]) >> 16) & 65535;
    
    int lo_lo = a_lo_lo + 1;
    int carry = (lo_lo >> 16) & 1;
    
    int lo_hi = a_lo_hi + carry;
    carry = (lo_hi >> 16) & 1;
    
    r[1] = ((lo_hi & 65535) << 16) | (lo_lo & 65535);
    r[0] = (~n[0]) + carry;
}

void print_num(int n[]) {
    if (n[0] == 0 && n[1] == 0) {
        out('0', 0);
        return;
    }
    
    int is_neg = 0;
    if (n[0] & -2147483648) {
        is_neg = 1;
    } else if (n[0] < 0) {
        is_neg = 1;
    }
    
    if (is_neg) {
        out('-', 0);
        int pos_hi = ~n[0];
        int pos_lo = ~n[1];
        
        pos_lo = pos_lo + 1;
        if (pos_lo == 0) {
            pos_hi = pos_hi + 1;
        }
        print_abs_val(pos_hi, pos_lo);
    } else {
        print_abs_val(n[0], n[1]);
    }
}

int main() {
    // a = 4294967796 (1 * 2^32 + 500)
    a[0] = 1;
    a[1] = 500;

    // b = 8589936092 (2 * 2^32 + 1500)
    b[0] = 2;
    b[1] = 1500;

    // res = a + b
    add_64(a, b, res);

    // Expected result: 12884903888 (3 * 2^32 + 2000)
    print_num(res);

    return 0;
}