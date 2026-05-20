
void print_string(int str[]){
    int size = str[0];
    int i = 1;
    while (i <= size) {
        out(str[i], 0);
        i = i + 1;
    }
}

int string[] = "hello world";

int main() {
    print_string(string);
    return 0;
}