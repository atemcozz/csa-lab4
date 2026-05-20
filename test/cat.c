
void print_string(int str[]){
    int size = str[0];
    int i = 1;
    while (i <= size) {
        out(str[i], 0);
        i = i + 1;
    }
}

int done = 0;
__interrupt__(0)
void handle_input_data(){
    out(in(0), 0);
}


__interrupt__(1)
void handle_input_end(){
    int ch = in(1);
    if (ch) {
        done = 1;
        return;
    }
}

int main() {
    while (!done) {
        // wait for input
    }
    return 0;
}