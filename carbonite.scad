file = "asdf.stl";
xin = 200;
yin = 200;

echo(file);

h = 4;
w = 25;
b = 1.5;
ratio = (w-b*2)/xin;
l = yin*ratio+b*2;


difference() {
    union() {
        translate([0,0,h/2]) scale([ratio,ratio,ratio]) import_stl(file);
        translate([-w/2,-l/2,0]) cube([w,l,h]);
    }
    translate([0,0,-40]) cylinder(h=40,r=100);
}
