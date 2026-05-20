
void print_string(int str[]){
    int size = str[0];
    int i = 1;
    while (i <= size) {
        out(str[i], 0);
        i = i + 1;
    }
}


void print_int(int num) {
    int ch = 0;

    if (num == 0) {
        out('0', 0);
        return;
    }
    
    if (num < 0) {
        out('-', 0);
        num = -num;
    }

    int buf[12];
    int i = 1;
    while (num > 0) {
        buf[i] = num % 10 + '0';
        i = i + 1;
        num = num / 10;
    }
    i = i - 1;
    while (i > 0) {
        out(buf[i], 0);
        i = i - 1;
    }

}
int main() {
    print_string("Hello, world!");
    print_int(12345);
    print_int(-67890);
    return 0;
}