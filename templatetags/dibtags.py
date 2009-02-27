from django.template import Library, Node, TemplateSyntaxError, \
    resolve_variable, VariableDoesNotExist
from django.newforms.util import flatatt
from django.conf import settings
import Image, md5
from mx.Misc.OrderedMapping import OrderedMapping 

register = Library()

# img tag # {{{
class ImgNode(Node):
    def __init__(self, parts):
        self.params = self.clean(parts)

    def clean(self, parts):
        """ validates the content, and returns a dict """
        d = {}
        for part in parts:
            try:
                name, value = part.split("=", 1)
            except ValueError:
                raise TemplateSyntaxError, "Syntax Error, part: %s" % part
            d[name] = value
        if "src" not in d:
            raise TemplateSyntaxError, "SRC attribute is mandatory"
        return d

    def get(self, key, context, default=""):
        if not key in self.params: return default
        try:
            return resolve_variable(str(self.params[key]), context)
        except VariableDoesNotExist:
            return str(self.params[key]) 
        except Exception, e: print "big problem", e, "while key=", key

    def digest(self, context):
        """ returns a dict with varaibles resolved """
        d = {}
        for key, value in self.params.iteritems():
            d[key] = self.get(key, context)
        return d

    def render(self, context):
        d = dict(self.digest(context))
        return """<img src="/static2/clear.gif" style="background-image:url(%(src)s); background-position:%(pos-x)s %(pos-y)s; width:%(width)s; height:%(height)s">""" % d
    
#@register.tag()
def img(parser, token):
    return ImgNode(token.split_contents()[1:])
img = register.tag(img) 
# }}}

# imgbundle tag # {{{
class ImgBundleNode(Node):
    def __init__(self, nodelist):
        self.nodelist = nodelist
    def render(self, context):
        # the main magic happens here
        imgs = {}
        names = []
        for imgnode in self.nodelist.get_nodes_by_type(ImgNode):
            src = imgnode.get("src", context)
            imgs.setdefault(src, [])
            imgs[src].append(imgnode)
            names.append("%s:%s:%s" % (src, imgnode.params.get("width",""), imgnode.params.get("height","")))
        names = "".join(names)
        img_name = "/static2/%s.jpg" % md5.new(names).hexdigest()
        current_x = 0
        max_y = 0
        final_images = OrderedMapping()
        for src, nodelist in imgs.iteritems():
            # as of now we only support images that are in /static/
            m = Image.open(settings.SETTINGS_FILE_FOLDER.joinpath('static').joinpath(src.split("/")[-1])).convert("RGB")
            for n in nodelist:
                n.params["src"], n.params["pos-y"] = img_name, 0
                # there are 4 cases: 
                if not n.params.get("width") and not n.params.get("height"):
                    # neither width nor height is set
                    w, h = m.size
                elif not n.params.get("width") and n.params.get("height"):
                    # width not given, but height given
                    w, h = ((m.size[0] * 1.0) / m.size[1]) * int(n.params["height"][1:-3]), int(n.params["height"][1:-3])
                elif n.params.get("width") and not n.params.get("height"):
                    w, h = int(n.params["width"][1:-3]), ((m.size[1] * 1.0) / m.size[0]) * int(n.params["width"][1:-3])
                else:
                    w, h = int(n.params["width"][1:-3]), int(n.params["height"][1:-3])
                if final_images.has_key("%s:%s:%s" % (src, w, h)):
                    i, pos_x = final_images["%s:%s:%s" % (src, w, h)]
                else:
                    new_image = m.resize((w, h), Image.ANTIALIAS)
                    final_images["%s:%s:%s" % (src, w, h)] = (new_image, current_x)
                    pos_x = current_x
                    current_x += new_image.size[0]
                    if max_y < new_image.size[1]: max_y = new_image.size[1]
                n.params["width"], n.params["height"], n.params["pos-x"] = (w, h, -pos_x)
        if not settings.SETTINGS_FILE_FOLDER.joinpath('static').joinpath(img_name.split("/")[-1]).exists():
            n = Image.new("RGB", (current_x, max_y))
            print final_images, current_x
            for k in final_images.keys():
                i, p = final_images[k]
                n.paste(i, (p, 0, p + i.size[0], i.size[1])) 
            n.save(settings.SETTINGS_FILE_FOLDER.joinpath('static').joinpath(img_name.split("/")[-1]))
        return self.nodelist.render(context)

#@register.tag()
def imgbundle(parser, token):
    """
        For optimizing page load in browser, the number of http requests to 
        server should be minimized. Javascripts can be bundled, or inlined in
        the html page, and so can be CSS, but there is no way to include images.
        Further, in a typical page, there are a lot of small images, icons for
        example, that lead to a lot of http request by browser. 

        It is a well known optimization to bundle all the images into one, in 
        this case, we join the images end to end horizontally, and create a 
        single image, that will be fetched by the browser, and we will use CSS
        to make sure they line up.

        Put 
            {% imgbundle %}
        at the beginning of the page, and 
            {% endimgbundle %}
        near the bottom. 
        
        Instead of using <img>, use, {% img %} tag, which takes the same 
        parameters as <img> html tag. 

    """
    nodelist = parser.parse(('endimgbundle', ))
    parser.delete_first_token()
    return ImgBundleNode(nodelist)

imgbundle = register.tag(imgbundle) 
# }}}
