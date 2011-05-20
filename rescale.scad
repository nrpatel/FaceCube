file = "asdf.stl";
xin = 200;
yin = 200;

echo(file);

w = 40;
ratio = w/max(xin,yin);

difference() {
    translate([0,0,-2]) scale([ratio,ratio,ratio]) import_stl(file);
    translate([0,0,-40]) cylinder(h=40,r=100);
}
